# misconception_classifier/split.py
import argparse
import logging
import os
import pandas as pd
import numpy as np
from typing import Tuple
from itertools import combinations

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def tiered_weighted_variant_split(
    df: pd.DataFrame, 
    test_ratio: float = 0.2, 
    min_train: int = 20, 
    min_test: int = 1, 
    soft_test_min: int = 5
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits the dataset using a greedy combinatorial approach based on QuestionId and MC_Answer variants,
    ensuring minimum class constraints are respected across both splits.
    """
    logging.info("Initializing tiered weighted variant split...")
    
    global_counts = df['Misconception'].value_counts().to_dict()
    min_total_required = min_train + min_test

    train_allocated = {m: 0 for m in global_counts}
    test_allocated = {m: 0 for m in global_counts}

    # 1. Extract variants grouped by Question
    questions_data = []
    for qid, q_group in df.groupby('QuestionId'):
        variants = []
        for ans, v_group in q_group.groupby('MC_Answer'):
            variants.append({
                'ans': ans,
                'counts': v_group['Misconception'].value_counts().to_dict(),
                'indices': v_group.index.tolist(),
                'size': len(v_group)
            })

        c_score = 0
        for v in variants:
            for m, c in v['counts'].items():
                g_c = global_counts[m]
                if g_c == 0: 
                    continue
                if g_c < min_total_required:
                    c_score += 10.0
                else:
                    slack = g_c - min_total_required
                    c_score += 1000.0 / (slack + 1)

        questions_data.append({
            'qid': qid,
            'variants': variants,
            'criticality': c_score
        })

    # Sort questions by how critically they contain rare classes
    questions_data.sort(key=lambda x: x['criticality'], reverse=True)

    train_idx, test_idx = [], []

    # 2. Greedy Assignment with Tiered Constraints
    logging.info(f"Assigning {len(questions_data)} question variants to splits...")
    
    for q in questions_data:
        variants = q['variants']
        n = len(variants)

        best_partition = None
        best_score = float('inf')

        valid_partitions = []
        indices = list(range(n))
        for i in range(n + 1):
            for train_v_idx in combinations(indices, i):
                train_set = [variants[idx] for idx in train_v_idx]
                test_set = [variants[idx] for idx in indices if idx not in train_v_idx]
                valid_partitions.append((train_set, test_set))

        for train_set, test_set in valid_partitions:
            temp_train = train_allocated.copy()
            temp_test = test_allocated.copy()

            for v in train_set:
                for m, c in v['counts'].items(): 
                    temp_train[m] += c
            for v in test_set:
                for m, c in v['counts'].items(): 
                    temp_test[m] += c

            score = 0
            for m, g_count in global_counts.items():
                if g_count == 0: 
                    continue

                if g_count >= min_total_required:
                    weight_factor = g_count

                    # --- TIER 1A: Train Starvation (FATAL) ---
                    max_allowed_test = g_count - min_train
                    if temp_test[m] > max_allowed_test:
                        score += 1e8 * (temp_test[m] - max_allowed_test) * weight_factor

                    # --- TIER 1B: Test Starvation (FATAL) ---
                    max_allowed_train = g_count - min_test
                    if temp_train[m] > max_allowed_train:
                        score += 1e8 * (temp_train[m] - max_allowed_train) * weight_factor

                    # --- TIER 2: Soft Test Minimum (STRONG SUGGESTION) ---
                    target_test_min = min(soft_test_min, max_allowed_test)
                    if temp_test[m] < target_test_min:
                        shortfall = target_test_min - temp_test[m]
                        score += 1e7 * shortfall * weight_factor

                    # --- TIER 3: Target balance (GENERAL VIBE) ---
                    t_target = g_count * (1 - test_ratio)
                    te_target = g_count * test_ratio

                    train_err = ((temp_train[m] - t_target) / (t_target + 1)) ** 2
                    test_err = ((temp_test[m] - te_target) / (te_target + 1)) ** 2
                    score += (train_err + test_err) * 10

                else:
                    # Doomed classes just go to train
                    if temp_test[m] > 0:
                        score += 1e8 * temp_test[m]

            # Penalize completely empty splits slightly to encourage mixing if possible
            if len(train_set) == 0 or len(test_set) == 0:
                score += 500

            if score < best_score:
                best_score = score
                best_partition = (train_set, test_set)

        best_train, best_test = best_partition
        for v in best_train:
            train_idx.extend(v['indices'])
            for m, c in v['counts'].items(): 
                train_allocated[m] += c
        for v in best_test:
            test_idx.extend(v['indices'])
            for m, c in v['counts'].items(): 
                test_allocated[m] += c

    return df.loc[train_idx].copy(), df.loc[test_idx].copy()


def print_split_report(train_df: pd.DataFrame, test_df: pd.DataFrame, min_train: int, min_test: int):
    """Generates a terminal-friendly report of the split logic, replacing Jupyter's display()."""
    
    merged_df = (
        pd.concat(
        [train_df['Misconception'].value_counts(),
         test_df['Misconception'].value_counts()],
        axis=1,
        keys=['Train_Count', 'Test_Count'])
        .fillna(0)
        .astype(int)
    )

    merged_df['Total'] = merged_df['Train_Count'] + merged_df['Test_Count']
    merged_df['Status'] = np.where(
        (merged_df['Train_Count'] >= min_train) & (merged_df['Test_Count'] >= min_test),
        'OK',
        'DELETE'
    )

    cols = ['Total', 'Train_Count', 'Test_Count', 'Status']
    merged_df = merged_df[cols].sort_values(by='Total', ascending=False)
    
    logging.info(f"\nVariant Holdout Split: Train: {len(train_df)} rows | Test: {len(test_df)} rows")
    logging.info("\n" + merged_df.to_string())
    
    deletions = merged_df[merged_df['Status'] == 'DELETE']
    if not deletions.empty:
        logging.warning(f"{len(deletions)} classes failed to meet the min_train/min_test threshold.")


def main(input_csv: str, train_out: str, test_out: str, test_ratio: float, min_train: int, min_test: int, soft_test_min: int):
    logging.info(f"Reading source data from {input_csv}...")
    df = pd.read_csv(input_csv)
    
    train_df, test_df = tiered_weighted_variant_split(
        df=df,
        test_ratio=test_ratio,
        min_train=min_train,
        min_test=min_test,
        soft_test_min=soft_test_min
    )
    
    print_split_report(train_df, test_df, min_train, min_test)
    
    
    os.makedirs(os.path.dirname(train_out), exist_ok=True)
    
    import csv # required for strict quoting
    logging.info(f"Saving Train split to {train_out}...")
    train_df.to_csv(train_out, index=False, quoting=csv.QUOTE_ALL)
    
    logging.info(f"Saving Test split to {test_out}...")
    test_df.to_csv(test_out, index=False, quoting=csv.QUOTE_ALL)
    
    logging.info("Splitting pipeline completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Custom tiered weighted variant splitter.")
    parser.add_argument("--input", required=True, help="Path to cleaned/prepped map_prepared.csv")
    parser.add_argument("--train_out", required=True, help="Path to save train_main.csv")
    parser.add_argument("--test_out", required=True, help="Path to save val_main.csv")
    parser.add_argument("--test_ratio", type=float, default=0.2, help="Target ratio for test split")
    parser.add_argument("--min_train", type=int, default=20, help="Absolute minimum samples required in train set")
    parser.add_argument("--min_test", type=int, default=1, help="Absolute minimum samples required in test set")
    parser.add_argument("--soft_test_min", type=int, default=5, help="Target minimum samples for test set if possible")
    
    args = parser.parse_args()
    
    main(
        input_csv=args.input,
        train_out=args.train_out,
        test_out=args.test_out,
        test_ratio=args.test_ratio,
        min_train=args.min_train,
        min_test=args.min_test,
        soft_test_min=args.soft_test_min
    )

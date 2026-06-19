import os
import csv
import yaml
import argparse
import logging
import pandas as pd
from sklearn.model_selection import train_test_split

# Import the new tiered splitter we created in the previous step
# (Make sure split.py is in the same directory as this file)
from misconception_classifier.split import tiered_weighted_variant_split

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def load_yaml_dict(filepath: str) -> dict:
    """Loads a YAML configuration file into a Python dictionary."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Configuration file not found at: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def clean_and_relabel(df: pd.DataFrame, rename_dict: dict) -> pd.DataFrame:
    """Applies target isolation, NaN filling, relabeling, and text cleaning."""
    # Take only incorrect categories
    df = df[~df['Category'].isin(['True_Correct', 'False_Correct'])].copy()

    # Fill NaNs with Unclassified_Error
    df['Misconception'] = df['Misconception'].fillna('Unclassified_Error').astype(str)

    # Relabeling using external dictionary
    df['Misconception'] = df['Misconception'].replace(rename_dict)

    # Prevent hidden newline CSV bugs
    text_columns = ['QuestionText', 'MC_Answer', 'StudentExplanation']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[\r\n]+', ' ', regex=True)
            
    return df

def split_stratified_legacy(df: pd.DataFrame, test_size: float, seed: int):
    """The original stratified split, requiring >= 10 samples per class."""
    class_counts = df['Misconception'].value_counts()
    valid_classes = class_counts[class_counts >= 10].index.tolist()
    
    # Filter out ultra-rare classes
    df_filtered = df[df['Misconception'].isin(valid_classes)].copy()
    
    dropped_rows = len(df) - len(df_filtered)
    if dropped_rows > 0:
        logging.warning(f"Dropped {dropped_rows} rows from classes with < 10 samples.")

    train_df, test_df = train_test_split(
        df_filtered,
        test_size=test_size,
        random_state=seed,
        stratify=df_filtered['Misconception']
    )
    return train_df, test_df

def main(args):
    logging.info(f"Loading configuration from {args.config_path}...")
    rename_dict = load_yaml_dict(args.config_path)
    
    logging.info(f"Loading raw data from {args.input}...")
    raw_df = pd.read_csv(args.input)

    logging.info("Cleaning and relabeling data...")
    df_prep = clean_and_relabel(raw_df, rename_dict)

    if args.prep_out:
        os.makedirs(os.path.dirname(args.prep_out), exist_ok=True)
        df_prep.to_csv(args.prep_out, index=False, quoting=csv.QUOTE_ALL)
        logging.info(f"Prepared intermediate data saved to: {args.prep_out}")

    logging.info(f"Splitting data using '{args.split_method}' method...")
    
    if args.split_method == "stratified":
        train_df, test_df = split_stratified_legacy(
            df_prep, 
            test_size=args.test_size, 
            seed=args.seed
        )
    elif args.split_method == "tiered":
        train_df, test_df = tiered_weighted_variant_split(
            df_prep, 
            test_ratio=args.test_size, 
            min_train=20, 
            min_test=1, 
            soft_test_min=5
        )
    else:
        raise ValueError(f"Unknown split method: {args.split_method}")

    logging.info(f"Train set size: {len(train_df)} rows")
    logging.info(f"Test set size:  {len(test_df)} rows")

    os.makedirs(os.path.dirname(args.train_out), exist_ok=True)
    os.makedirs(os.path.dirname(args.test_out), exist_ok=True)

    train_df.to_csv(args.train_out, index=False, quoting=csv.QUOTE_ALL)
    test_df.to_csv(args.test_out, index=False, quoting=csv.QUOTE_ALL)
    logging.info("✅ Data successfully locked and safely saved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Preparation and Splitting Module")
    
    # File Paths
    parser.add_argument("--input", type=str, default="data/map_train.csv", help="Path to raw training data")
    parser.add_argument("--prep_out", type=str, default="data/map_prepared.csv", help="Path to save intermediate prepped data")
    parser.add_argument("--train_out", type=str, default="data/train_main.csv", help="Path to save final train split")
    parser.add_argument("--test_out", type=str, default="data/val_main.csv", help="Path to save final test/val split")
    parser.add_argument("--config_path", type=str, default="config/simple_relabel.yaml", help="Path to yaml relabel config")
    
    # Splitting Parameters
    parser.add_argument("--split_method", type=str, choices=["stratified", "tiered"], default="tiered", 
                        help="Choose 'stratified' (legacy 95/5) or 'tiered' (new custom variant split)")
    parser.add_argument("--test_size", type=float, default=0.05, help="Test set ratio (e.g., 0.05 for 5%)")
    parser.add_argument("--seed", type=int, default=99, help="Random seed for legacy stratified split")

    args = parser.parse_args()
    main(args)

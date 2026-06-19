# misconception_classifier/embed.py
import argparse
import logging
import os
import yaml
import random
import pandas as pd
import numpy as np
from torch.utils.data import DataLoader
from sentence_transformers import SentenceTransformer, InputExample, losses

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def load_yaml_dict(filepath: str) -> dict:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Configuration file not found at: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def main(args):
    # 1. Load Data
    logging.info(f"Loading configurations and data...")
    class_definitions = load_yaml_dict(args.config_path)
    train_df = pd.read_csv(args.train_in)
    val_df = pd.read_csv(args.val_in)

    # Filter definitions to only include classes present in the train set
    present_classes = train_df['Misconception'].unique().tolist()
    filtered_class_defs = {k: v for k, v in class_definitions.items() if k in present_classes}
    class_names = list(filtered_class_defs.keys())

    # 2. Generate Contrastive Pairs
    logging.info("Generating Contrastive Training Pairs...")
    train_examples = []
    
    # Fix random seed for reproducibility in sampling negative pairs
    random.seed(args.seed)

    for _, row in train_df.iterrows():
        true_class = str(row['Misconception'])
        if true_class not in filtered_class_defs:
            continue

        q = row['QuestionText']
        a = row['MC_Answer']
        e = row['StudentExplanation']
        student_text = f"Question: {q} | Chosen Answer: {a} | Student Explanation: {e}"

        correct_def = filtered_class_defs[true_class]

        # POSITIVE PAIR (Label 1.0)
        train_examples.append(InputExample(texts=[correct_def, student_text], label=1.0))

        # EXPLICIT NEGATIVE PAIRS (Label 0.0)
        wrong_classes = [c for c in class_names if c != true_class]
        sampled_wrong = random.sample(wrong_classes, min(args.neg_pairs, len(wrong_classes)))
        for wrong_class in sampled_wrong:
            wrong_def = filtered_class_defs[wrong_class]
            train_examples.append(InputExample(texts=[wrong_def, student_text], label=0.0))

    logging.info(f"Created {len(train_examples)} Contrastive Training Pairs.")

    # 3. Fine-Tune Embedder
    logging.info(f"Loading Base Model: {args.base_model}...")
    model = SentenceTransformer(args.base_model, trust_remote_code=True)
    
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=args.batch_size)
    train_loss = losses.CosineSimilarityLoss(model=model)

    logging.info(f"Fine-Tuning Semantic Space for {args.epochs} Epochs...")
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=args.epochs,
        warmup_steps=100,
        show_progress_bar=True
    )

    # Save the fine-tuned model artifact
    os.makedirs(args.model_out, exist_ok=True)
    model.save(args.model_out)
    logging.info(f"Fine-tuned Embedder saved to: {args.model_out}")

    # 4. Generate Embeddings
    logging.info("Generating Final Dense Embeddings...")
    
    def get_texts(df):
        return [
            f"Question: {row['QuestionText']} | Chosen Answer: {row['MC_Answer']} | Student Explanation: {row['StudentExplanation']}"
            for _, row in df.iterrows()
        ]

    X_train_texts = get_texts(train_df)
    X_val_texts = get_texts(val_df)

    # convert_to_numpy=True bypasses the need to manually send tensors back to CPU
    X_train_emb = model.encode(X_train_texts, convert_to_numpy=True, show_progress_bar=True)
    X_val_emb = model.encode(X_val_texts, convert_to_numpy=True, show_progress_bar=True)

    os.makedirs(os.path.dirname(args.train_emb_out), exist_ok=True)
    np.save(args.train_emb_out, X_train_emb)
    np.save(args.val_emb_out, X_val_emb)
    
    logging.info(f"Embeddings saved to {args.train_emb_out} and {args.val_emb_out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_in", required=True, help="Path to train_main.csv")
    parser.add_argument("--val_in", required=True, help="Path to val_main.csv")
    parser.add_argument("--config_path", required=True, help="Path to dictionary yaml")
    parser.add_argument("--base_model", default="sentence-transformers/all-mpnet-base-v2")
    parser.add_argument("--model_out", default="models/finetuned_mpnet")
    parser.add_argument("--train_emb_out", required=True, help="Path to output train .npy")
    parser.add_argument("--val_emb_out", required=True, help="Path to output val .npy")
    
    # Hyperparameters
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--neg_pairs", type=int, default=2, help="Num negative pairs per row")
    parser.add_argument("--seed", type=int, default=42)
    
    args = parser.parse_args()
    main(args)

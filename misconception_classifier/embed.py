# misconception_classifier/embed.py
import argparse
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import os

MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'

def main(input_csv, output_npy):
    print(f"Reading {input_csv}...")
    df = pd.read_csv(input_csv)
    
    text_input = (
        "Problem: " + df['QuestionText'] +
        " | Answer Chosen: " + df['MC_Answer'].astype(str) +
        " | Explanation: " + df['StudentExplanation']
    )
    
    print("Encoding text...")
    embedder = SentenceTransformer(MODEL_NAME)
    embeddings = embedder.encode(text_input.tolist(), show_progress_bar=True)
    
    # Save as an independent artifact
    os.makedirs(os.path.dirname(output_npy), exist_ok=True)
    np.save(output_npy, embeddings)
    print(f"Embeddings saved to {output_npy}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", required=True, help="Path to save embeddings (.npy)")
    args = parser.parse_args()
    main(args.input, args.output)

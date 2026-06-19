# misconception_classifier/train.py
import argparse
import json
import logging
import os
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main(args):
    logging.info(f"Loading training data from {args.features} and {args.labels}...")
    X_train = np.load(args.features)
    df_train = pd.read_csv(args.labels)
    y_train = df_train['Misconception'].reset_index(drop=True)

    logging.info(f"Loading hyperparameters from {args.params}...")
    with open(args.params, 'r') as f:
        best_params = json.load(f)

    # Convert to CatBoost Pool
    train_pool = Pool(X_train, y_train)

    # Initialize model with best params
    model = CatBoostClassifier(
        **best_params,
        loss_function="MultiClass",
        task_type="GPU" if args.use_gpu else "CPU",
        verbose=100  # Print progress
    )

    logging.info("Fitting final CatBoost model on full training set...")
    model.fit(train_pool)

    # Save model locally as an artifact
    os.makedirs(os.path.dirname(args.output_model), exist_ok=True)
    model.save_model(args.output_model)
    logging.info(f"Final Model successfully saved to {args.output_model}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True, help="Path to train .npy embeddings")
    parser.add_argument("--labels", required=True, help="Path to train .csv labels")
    parser.add_argument("--params", required=True, help="Path to best_params.json")
    parser.add_argument("--output_model", required=True, help="Path to save output .cbm file")
    
    parser.add_argument("--use_gpu", action="store_true", help="Pass this flag to use GPU")
    
    args = parser.parse_args()
    main(args)

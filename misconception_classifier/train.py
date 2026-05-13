# misconception_classifier/train.py
import argparse
import json
import numpy as np
import pandas as pd
import mlflow
import os
from catboost import CatBoostClassifier, Pool

HARDWARE = "GPU" #or CPU

def main(features_npy, labels_csv, params_json, output_model):
    print(f"Loading data from {features_npy} and {labels_csv}...")
    X_train = np.load(features_npy)
    df_train = pd.read_csv(labels_csv)
    y_train = df_train['Misconception'].reset_index(drop=True)

    print(f"Loading parameters from {params_json}...")
    with open(params_json, 'r') as f:
        best_params = json.load(f)

    # Set up MLflow to track the final training run
    mlflow.set_experiment("Math_Misconception_Training")
    with mlflow.start_run(run_name="Final_Model_Train"):
        # Log the chosen parameters
        mlflow.log_params(best_params)

        train_pool = Pool(X_train, y_train)

        # Initialize model with best params + standard fixed params
        model = CatBoostClassifier(
            **best_params,
            loss_function="MultiClass",
            task_type=HARDWARE, # Change to GPU if executing on a CUDA-enabled machine
            verbose=100      # Print every 100th iteration to monitor progress
        )

        print("Training final model...")
        model.fit(train_pool)

        # 1. Save model locally as an artifact
        os.makedirs(os.path.dirname(output_model), exist_ok=True)
        model.save_model(output_model)
        print(f"Model saved to {output_model}")

        # 2. Log model to MLflow registry
        mlflow.catboost.log_model(model, artifact_path="catboost_model")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True, help="Path to train .npy embeddings")
    parser.add_argument("--labels", required=True, help="Path to train .csv labels")
    parser.add_argument("--params", required=True, help="Path to best_params.json")
    parser.add_argument("--output_model", required=True, help="Path to save output .cbm file")
    args = parser.parse_args()
    main(args.features, args.labels, args.params, args.output_model)

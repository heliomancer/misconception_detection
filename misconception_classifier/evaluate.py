# misconception_classifier/evaluate.py
import argparse
import json
import numpy as np
import pandas as pd
import mlflow
import os
from catboost import CatBoostClassifier, Pool
from sklearn.metrics import accuracy_score, f1_score

def main(features_npy, labels_csv, model_path, output_metrics):
    print(f"Loading test data from {features_npy} and {labels_csv}...")
    X_test = np.load(features_npy)
    df_test = pd.read_csv(labels_csv)
    y_test = df_test['Misconception'].reset_index(drop=True)

    print(f"Loading model from {model_path}...")
    model = CatBoostClassifier()
    model.load_model(model_path)

    print("Generating predictions...")
    test_pool = Pool(X_test, y_test)
    preds = model.predict(test_pool)
    
    # Flatten the 2D array output of CatBoost MultiClass
    preds_flat = [p[0] for p in preds]

    # Calculate metrics
    metrics = {
        "f1_macro": f1_score(y_test, preds_flat, average='macro'),
        "f1_weighted": f1_score(y_test, preds_flat, average='weighted'),
        "accuracy": accuracy_score(y_test, preds_flat)
    }

    # 1. Save metrics to disk
    os.makedirs(os.path.dirname(output_metrics), exist_ok=True)
    with open(output_metrics, 'w') as f:
        json.dump(metrics, f, indent=4)
    
    print("EVALUATION RESULTS:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")
    print(f"Metrics saved to {output_metrics}")

    # 2. Log metrics to MLflow
    mlflow.set_experiment("Math_Misconception_Evaluation")
    with mlflow.start_run(run_name="Final_Model_Eval"):
        mlflow.log_metrics(metrics)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True, help="Path to test .npy embeddings")
    parser.add_argument("--labels", required=True, help="Path to test .csv labels")
    parser.add_argument("--model", required=True, help="Path to trained .cbm model")
    parser.add_argument("--output_metrics", required=True, help="Path to save metrics.json")
    args = parser.parse_args()
    main(args.features, args.labels, args.model, args.output_metrics)

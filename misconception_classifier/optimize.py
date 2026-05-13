# misconception_classifier/optimize.py
import argparse
import json
import numpy as np
import pandas as pd
import optuna
import mlflow
from catboost import CatBoostClassifier, Pool
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score

HARDWARE = 'GPU' # or 'CPU'
OPTUNA_SEED = 77

def main(features_npy, labels_csv, output_json):
    # Load independent artifacts
    X_emb = np.load(features_npy)
    df = pd.read_csv(labels_csv)
    y = df['Misconception'].reset_index(drop=True)

    mlflow.set_experiment("Math_Misconception_Optuna")

    def objective(trial):
        # We start an MLflow run for EACH Optuna trial
        with mlflow.start_run(nested=True):
            params = {
                "iterations": trial.suggest_int("iterations", 400, 1200),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "depth": trial.suggest_int("depth", 4, 8),
                "loss_function": "MultiClass",
                "task_type": HARDWARE, # Adjust to GPU if available
                "verbose": 0
            }
            mlflow.log_params(params) # Track in MLflow

            skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=OPTUNA_SEED)
            f1_scores =[]

            for tr_idx, va_idx in skf.split(X_emb, y):
                train_pool = Pool(X_emb[tr_idx], y.iloc[tr_idx])
                val_pool = Pool(X_emb[va_idx], y.iloc[va_idx])

                model = CatBoostClassifier(**params)
                model.fit(train_pool, eval_set=val_pool, early_stopping_rounds=50)

                preds = [p[0] for p in model.predict(val_pool)]
                f1_scores.append(f1_score(y.iloc[va_idx], preds, average='macro'))

            mean_f1 = np.mean(f1_scores)
            mlflow.log_metric("cv_f1_macro", mean_f1) # Track metric in MLflow
            
            return mean_f1

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=10)

    # Save best parameters to a JSON file for the trainer to use
    with open(output_json, 'w') as f:
        json.dump(study.best_params, f, indent=4)
    print(f"Best parameters saved to {output_json}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--output_json", required=True)
    args = parser.parse_args()
    main(args.features, args.labels, args.output_json)

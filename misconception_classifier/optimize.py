# misconception_classifier/optimize.py
import argparse
import json
import logging
import numpy as np
import pandas as pd
import optuna
from catboost import CatBoostClassifier, Pool
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import f1_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main(args):
    logging.info(f"Loading features from {args.features}...")
    X_emb = np.load(args.features)
    
    logging.info(f"Loading labels from {args.labels}...")
    df = pd.read_csv(args.labels)
    y = df['Misconception'].reset_index(drop=True)

    def objective(trial):
        params = {
            "iterations": trial.suggest_int("iterations", 500, 1500),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "depth": trial.suggest_int("depth", 4, 8),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 2, 10),
            "auto_class_weights": trial.suggest_categorical("auto_class_weights", ["Balanced", "SqrtBalanced", "None"]),
            "loss_function": "MultiClass",
            "eval_metric": "TotalF1",
            "task_type": "GPU" if args.use_gpu else "CPU",
            "random_seed": args.seed,
            "verbose": 0
        }

        skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=100)
        f1_scores = []

        for tr_idx, va_idx in skf.split(X_emb, y):
            train_pool = Pool(X_emb[tr_idx], y.iloc[tr_idx])
            val_pool = Pool(X_emb[va_idx], y.iloc[va_idx])

            model = CatBoostClassifier(**params)
            model.fit(train_pool, eval_set=val_pool, early_stopping_rounds=50)

            preds = [p[0] for p in model.predict(val_pool)]
            f1_scores.append(f1_score(y.iloc[va_idx], preds, average='macro'))

        return np.mean(f1_scores)

    optuna.logging.set_verbosity(optuna.logging.INFO)
    study = optuna.create_study(direction="maximize")
    
    logging.info(f"Starting {args.folds}-Fold Optuna Search for {args.n_trials} trials...")
    study.optimize(objective, n_trials=args.n_trials)

    logging.info("Best Parameters Found:")
    for k, v in study.best_params.items():
        logging.info(f"  {k}: {v}")

    # Save best parameters to a JSON file
    import os
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, 'w') as f:
        json.dump(study.best_params, f, indent=4)
        
    logging.info(f"Parameters saved to {args.output_json}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", required=True, help="Path to train .npy embeddings")
    parser.add_argument("--labels", required=True, help="Path to train .csv labels")
    parser.add_argument("--output_json", required=True, help="Path to output best_params.json")
    
    parser.add_argument("--n_trials", type=int, default=30)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use_gpu", action="store_true", help="Pass this flag to use task_type='GPU'")
    
    args = parser.parse_args()
    main(args)

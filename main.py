import pandas as pd

# Import modules
from misconception_classifier.embedder import get_embeddings
from misconception_classifier.optuna_searcher import find_best_params
from misconception_classifier.trainer import train_model
from misconception_classifier.evaluator import evaluate_model

def load_and_format_data(filepath: str):
    """Helper function to load CSV and create the unified Text_Input column."""
    df = pd.read_csv(filepath)
    text_input = (
        "Problem: " + df['QuestionText'] +
        " | Answer Chosen: " + df['MC_Answer'].astype(str) +
        " | Explanation: " + df['StudentExplanation']
    )
    return text_input.tolist(), df['Misconception']


def main():
    # Load Data
    print("Loading datasets...")
    X_train_texts, y_train = load_and_format_data("data/train_BLvsLLM.csv")
    X_test_texts, y_test = load_and_format_data("data/val_BLvsLLM.csv")
    print(f"Train size: {len(X_train_texts)} | Test size: {len(X_test_texts)}")

    # Embed Data
    X_train_emb = get_embeddings(X_train_texts, model_name='sentence-transformers/all-MiniLM-L6-v2')
    X_test_emb = get_embeddings(X_test_texts, model_name='sentence-transformers/all-MiniLM-L6-v2')

    # Find Best Parameters via Optuna
    best_params = find_best_params(X_train_emb, y_train, n_trials=30)

    # Train Final Model
    model = train_model(X_train_emb, y_train, best_params)

    # Evaluate
    metrics = evaluate_model(model, X_test_emb, y_test)

    # Optional: Save the model
    # model.save_model("data/best_catboost_model.cbm")


if __name__ == "__main__":
    main()

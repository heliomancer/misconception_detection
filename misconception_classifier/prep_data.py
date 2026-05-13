import os
import csv
import yaml
import pandas as pd
from sklearn.model_selection import train_test_split

# PATHS AND CONSTANTS
# ==========================================
# Options: "simple_relabel", "semantic_chatgpt", "semantic_chatgpt"
ACTIVE_RELABEL = "simple_relabel"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

RAW_DATA_PATH = os.path.join(DATA_DIR, "map_train.csv")
PREP_DATA_PATH = os.path.join(DATA_DIR, "map_prepared.csv")
TRAIN_OUT_PATH = os.path.join(DATA_DIR, "train_main.csv")
TEST_OUT_PATH = os.path.join(DATA_DIR, "val_main.csv")
DICT_PATH = os.path.join(CONFIG_DIR, f"{ACTIVE_RELABEL}.yaml")

SPLIT_SEED = 99 # For hold-out set reproducibility

# HELPER FUNCTIONS
# ==========================================
def load_yaml_dict(filepath: str) -> dict:
    """Loads a YAML configuration file into a Python dictionary."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Configuration file not found at: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

# MAIN SCRIPT
# ==========================================
if __name__ == "__main__":
    
    print("Loading configuration...")
    RENAME_DICT = load_yaml_dict(DICT_PATH)
    
    print("Loading raw data...")
    raw_train_df = pd.read_csv(RAW_DATA_PATH)

    # STEP 1: DATA PREPARATION AND CLEANING
    # ---------------------------------------------------------
    print("Cleaning and relabeling data...")
    
    # Take only incorrect categories: 'Misconception' and 'Neither'
    df = raw_train_df[~raw_train_df['Category'].isin(['True_Correct', 'False_Correct'])].copy()

    # Fill NaNs with Unclassified_Error (corresponds to 'Neither' category)
    df['Misconception'] = df['Misconception'].fillna('Unclassified_Error').astype(str)

    # Relabeling using our external dictionary
    df['Misconception'] = df['Misconception'].replace(RENAME_DICT)

    # Preventing the hidden newline CSV bug which breaks data loading
    text_columns = ['QuestionText', 'MC_Answer', 'StudentExplanation']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'[\r\n]+', ' ', regex=True)

    # Save prepared intermediate data
    df.to_csv(PREP_DATA_PATH, index=False, quoting=csv.QUOTE_ALL)
    print(f"Prepared data saved to: {PREP_DATA_PATH}")

    # STEP 2: DATA SPLITTING
    # ---------------------------------------------------------
    print("\nFiltering and splitting data...")
    
    # Reload prepared data 
    df = pd.read_csv(PREP_DATA_PATH)

    # Filter out ultra-rare classes (< 10 samples)
    class_counts = df['Misconception'].value_counts()
    valid_classes = class_counts[class_counts >= 10].index.tolist()
    df = df[df['Misconception'].isin(valid_classes)].copy()
    
    # NOTE: This eliminates the least populated classes ('Incorrect Equivalent Fraction Addition'
    # and 'Wrong Operation'), removing 15 objects from initial data.

    # Stratified split by misconception (95% Train / 5% Test)
    train_df, test_df = train_test_split(
        df,
        test_size=0.05,
        random_state=SPLIT_SEED,
        stratify=df['Misconception']
    )

    # Save split into .csv files with strict quoting
    train_df.to_csv(TRAIN_OUT_PATH, index=False, quoting=csv.QUOTE_ALL)
    test_df.to_csv(TEST_OUT_PATH, index=False, quoting=csv.QUOTE_ALL)

    print("\n✅ Data successfully locked and safely saved")
    print(f"Train set size: {len(train_df)} rows")
    print(f"Test set size: {len(val_df)} rows")

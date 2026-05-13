

# Math Misconception Classification 

> 🚧 **Work in Progress:** This repository contains the ongoing machine learning research for a Master's/ML thesis. 

##  Overview
This project serves as the machine learning backbone for an Intelligent Tutoring System (ITS). The goal is to accurately diagnose the specific mathematical misconception behind a student's incorrect answer based on text inputs.

**Dataset:** [EEDI MAP - Charting Student Math Misunderstandings](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/data). 


**Inputs:**
1. Math Problem Text
2. Student's Chosen Answer
3. Student's Text Explanation

## Project Structure
The repository is designed with a modern MLOps CLI architecture, separating data, configurations, and independent execution modules.

```text
.
├── config/                     <- .yaml configs for models and relabeling
├── data/                       <- Local data artifacts and LLM results 
│   ├── features/               <- Cached text embeddings (.npy)
│   └── *.csv                   <- Raw, prepped, and evaluation data
├── misconception_classifier/   <- Independent CLI modules for the ML pipeline
│   ├── prep_data.py            <- Data cleaning and train/val splitting
│   ├── embed.py                <- Generates dense embeddings
│   ├── optimize.py             <- Optuna hyperparameter search
│   ├── train.py                <- Fits the supervised classifier
│   ├── evaluate.py             <- Scores hold-out data
│   └── llm_val.py              <- Modular evaluation loop for LLM APIs
├── prompts/                    <- Markdown templates (zero-shot, few-shot, rulebook)
├── pyproject.toml              <- Dependency definitions (uv)
└── README.md
```

## Data Preparation & Filtering (`prep_data.py`)

The raw dataset (`map_train.csv`) requires strict preprocessing before it can be used for embeddings or LLM evaluation. The `prep_data.py` module handles this with the following pipeline:

1. **Dynamic Relabeling:** Target classes are mapped to human-readable strings using modular YAML configurations located in `config/`. This allows quick swapping of label semantics for LLM prompt engineering.
2. **Isolating Misconceptions:** Rows labeled `True_Correct` or `False_Correct` are dropped. The pipeline strictly trains and evaluates on incorrect answers. Null values are mapped to `Unclassified_Error`.
3. **Handling Rare Classes:** To ensure stable Cross-Validation, ultra-rare classes (fewer than 10 samples) are removed. 
4. **Stratified Splitting:** The final cleaned data is split into a 95% Training set and a 5% Hold-out Validation set that used for both supervised solution and LLM evaluation.

## Supervised Solution (Embeddings + CatBoost Classifier)

The primary and currently best-performing solution is a traditional supervised NLP pipeline. 

**Approach:** 
The Problem, Answer, and Explanation are concatenated into a single text block. This text is passed through a dense sentence embedder (`all-MiniLM-L6-v2`) to extract a 384-dimensional semantic vector. These embeddings are then fed into a highly tuned CatBoost classifier.

**Modular Pipeline:**
The pipeline is broken down into independent scripts that read and write file artifacts:
* `embed.py`: Processes the CSVs, runs the SentenceTransformer, and saves the outputs as `.npy` arrays. 
* `optimize.py`: Reads the `.npy` embeddings and runs a 3-Fold Stratified Cross-Validation using **Optuna** to find the optimal CatBoost hyperparameters, saving them to a JSON config.
* `train.py`: Takes the optimal parameters and embeddings to fit the final CatBoost model, outputting a `.cbm` artifact.
* `evaluate.py`: Generates predictions on the 5% hold-out validation set and calculates final metrics.

**Metrics (Hold-out Validation):**
| Model | Embedder | F1-Macro | F1-Weighted | Accuracy |
|-------|----------|----------|-------------|----------|
| TF-IDF Baseline + RF | N/A | 0.587 | 0.781 | 0.788 |
| **CatBoost (Main)** | `all-MiniLM-L6-v2` | **0.680** | **0.846** | **0.845** |

## LLM Solution (Generative API Validation)

To benchmark against modern generative AI, the project includes a robust pipeline to evaluate open-weights Large Language Models based purely on their reasoning capabilities.

**Prompting Approaches:**
We utilize `.md` files in the `prompts/` directory to cleanly separate prompt logic from Python code. Currently explored methods include:
* **Zero-Shot:** Providing the LLM with the task description, strict class definitions, and the raw input text.
* **Few-Shot + CoT:** Provides classes description with a few examples where the model is taught to output a "thought" (Chain-of-Thought reasoning diagnosing the math error) followed by a final "prediction".
* **Rulebook:** A dual-payload architecture. The heavy `rulebook_system.md` contains classes description and examples for every class (System prompt), while `rulebook_user.md` passes the dynamic object features (User prompt).

**API call module:**
`llm_val.py` helps orchestrate evaluating thousands of rows against remote API.
In this project **api.groq.com** free tier is used.
* **JSON Enforcement:** Forces models to return strict `{"thought": "...", "prediction": "..."}` schema.
* **Rate-Limit Handling:** Automatically pauses and retries when hitting Groq API RPM/RPD limits.
* **Stateful Execution:** Buffers and incrementally saves intermediate results to `data/llm_results_*.csv`. If the script crashes, it resumes exactly where it left off.
* **Multi-Model Iteration:** Evaluates a single data row against an array of models concurrently/sequentially to build comparative datasets.

**Best results (Rulebook prompt):**

| Model (via Groq) | F1-Macro | F1-Weighted | Accuracy |
|-------|----------|-------------|----------|
| `qwen/qwen3-32b` | 0.5110 | 0.7111 | 0.6972 |
| `openai/gpt-oss-120b` | 0.4277 | 0.6645 | 0.6338 |


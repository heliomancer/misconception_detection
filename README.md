***

# 🎓 Math Misconception Classification (Thesis Project)

> 🚧 **Work in Progress:** This repository contains the ongoing machine learning research for a Master's/ML thesis. 

## 1. 📌 Overview
This project serves as the machine learning backbone for an Intelligent Tutoring System (ITS). The goal is to accurately diagnose the specific mathematical misconception behind a student's incorrect answer based on text inputs.

**Dataset:** [EEDI MAP - Charting Student Math Misunderstandings](https://www.kaggle.com/competitions/map-charting-student-math-misunderstandings/data). 
*Note: This dataset uses a strict taxonomy of 35 specific misconception classes. It is highly imbalanced, with a vast majority of errors being 'Unclassified Error', requiring robust feature representation and handling of rare classes.*

**Inputs:**
1. Math Problem Text
2. Student's Chosen Answer
3. Student's Text Explanation

## 2. 📁 Project Structure
The repository is designed with a modern MLOps CLI architecture, separating data, configurations, and independent execution modules.

.
├── config/                             <- .yaml configs for relabeling and semantic matching
│   ├── semantic_chatgpt.yaml
│   ├── semantic_gemini.yaml
│   ├── semantic_large.yaml
│   └── simple_relabel.yaml
├── data/                               <- Local data artifacts (ignored in git)
│   ├── features/                       <- Cached text embeddings (.npy)
│   └── *.csv                           <- Raw, prepped, and evaluation data
├── misconception_classifier/           <- Independent CLI modules for the ML pipeline
│   ├── prep_data.py                    <- Data cleaning CLI orchestrator
│   ├── split.py                        <- Advanced tiered variant splitting logic
│   ├── embed.py                        <- Fine-tunes SentenceTransformer & generates embeddings
│   ├── optimize.py                     <- Optuna hyperparameter search
│   ├── train.py                        <- Fits the supervised CatBoost classifier
│   ├── evaluate.py                     <- Scores hold-out data
│   └── llm_val.py                      <- Modular evaluation loop for LLM APIs
├── prompts/                            <- Markdown templates for LLM evaluation
│   ├── few-shot.md
│   ├── rulebook_system.md
│   ├── rulebook_user.md
│   └── zero-shot.md
├── .gitignore
├── .python-version
├── Makefile                            <- Command orchestrator for the pipeline
├── pyproject.toml                      <- Dependency definitions (uv)
└── README.md

## 3. 🛠 Data Preparation & Filtering (`prep_data.py`)

The raw dataset (`map_train.csv`) requires strict preprocessing. 

1. **Dynamic Relabeling:** Target classes are mapped to human-readable strings using modular YAML configurations located in `config/`.
2. **Isolating Misconceptions:** Rows labeled `True_Correct` or `False_Correct` are dropped. The pipeline strictly trains and evaluates on incorrect answers. 
3. **Preventing Data Leakage (Tiered Variant Split):** A standard random split causes critical data leakage because identical multiple-choice variants for the same question can bleed across train and test sets. To fix this, we implemented a custom **Tiered Weighted Variant Split** (`split.py`) that strictly groups data by `QuestionId` and `MC_Answer`, greedily allocating entire variant groups while enforcing strict class population minimums. 

## 4. 🌳 Supervised Solution (Contrastive Fine-Tuning + CatBoost)

The primary solution is an advanced supervised NLP pipeline utilizing a fine-tuned semantic space.

**Approach:** 
The Problem, Answer, and Explanation are concatenated into a single text block. Instead of using a frozen embedder, we perform **Contrastive Fine-Tuning** on `all-mpnet-base-v2` using `CosineSimilarityLoss`. Positive pairs are formed by matching student text to the correct misconception definition. Negative pairs are explicitly sampled from incorrect class definitions. The fine-tuned 768-dimensional embeddings are then fed into a highly tuned CatBoost classifier.

**Metrics (Hold-out Validation):**

| Model Pipeline | F1-Macro | F1-Weighted | Accuracy (Micro F1) |
|-------|----------|-------------|----------|
| **Contrastive `all-mpnet-base-v2` + CatBoost** | **0.3006** | **0.74** | **0.7105** |

*A detailed classification report shows high accuracy on the majority `Unclassified Error` class (0.82 F1), with minority classes severely impacting the Macro average.*

## 5. 🤖 LLM Solution (Generative API Validation)

To benchmark against modern generative AI, the project includes a robust pipeline (`llm_val.py`) to evaluate open-weights Large Language Models based purely on their reasoning capabilities.

**Prompting Approaches:**
* **Zero-Shot:** Providing the LLM with the task description, strict class definitions, and the raw input text.
* **Few-Shot + CoT:** Provides class descriptions with examples where the model is taught to output a "thought" (diagnosing the math error) followed by a final "prediction".
* **Rulebook:** A dual-payload architecture. `rulebook_system.md` contains class descriptions and examples, while `rulebook_user.md` passes the dynamic object features.

**Best results (Rulebook prompt on un-split baseline):**
| Model (via Groq) | F1-Macro | F1-Weighted | Accuracy |
|-------|----------|-------------|----------|
| `qwen/qwen3-32b` | 0.5110 | 0.7111 | 0.6972 |
| `openai/gpt-oss-120b` | 0.4277 | 0.6645 | 0.6338 |

## 🚀 How to Run the Pipeline

This project uses `make` to orchestrate the pipeline and `uv` for dependency management. 

**1. Install Dependencies:**
```bash
uv sync
```

**2. Execute the Pipeline:**
You can run the entire ML pipeline step-by-step using the `Makefile` commands. *Note: The embedding step requires a GPU for contrastive fine-tuning.*

```bash
# Clean data and execute the strict Tiered Variant Split
make prep

# Fine-tune the SentenceTransformer and generate .npy embeddings
make embed

# Run 3-Fold Optuna Search to find best CatBoost hyperparameters
make optimize

# Train the final CatBoost classifier on the full train set
make train
```

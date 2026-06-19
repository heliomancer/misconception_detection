# Variables (Paths so we don't repeat ourselves)
DATA_DIR=data
FEATURES_DIR=$(DATA_DIR)/features
MODELS_DIR=models
CONFIG_DIR=config
DICT_YAML=$(CONFIG_DIR)/semantic_chatgpt.yaml

# 1. Prepare and Split Data
prep:
	uv run python misconception_classifier/prep_data.py \
		--config_path $(DICT_YAML) \
		--split_method tiered \
		--test_size 0.2

# 2. Fine-Tune Embedder & Generate .npy files
embed: prep
	uv run python misconception_classifier/embed.py \
		--train_in $(DATA_DIR)/train_main.csv \
		--val_in $(DATA_DIR)/val_main.csv \
		--config_path $(DICT_YAML) \
		--train_emb_out $(FEATURES_DIR)/train_emb.npy \
		--val_emb_out $(FEATURES_DIR)/val_emb.npy

# 3. Optimize CatBoost
optimize:
	uv run python misconception_classifier/optimize.py \
		--features $(FEATURES_DIR)/train_emb.npy \
		--labels $(DATA_DIR)/train_main.csv \
		--output_json $(CONFIG_DIR)/best_params.json \
		--n_trials 30 \
		--use_gpu

# 4. Train Final Classifier
train:
	uv run python misconception_classifier/train.py \
		--features $(FEATURES_DIR)/train_emb.npy \
		--labels $(DATA_DIR)/train_main.csv \
		--params $(CONFIG_DIR)/best_params.json \
		--output_model $(MODELS_DIR)/catboost_final.cbm \
		--use_gpu

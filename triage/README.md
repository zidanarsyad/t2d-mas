# Triage models and API usage

Triage does **not** call paid hosted inference APIs (for example, OpenAI or Anthropic), and it does not require API keys. Sentence embeddings and severity inference run locally using Sentence Transformers, scikit-learn, and Transformers.

Model downloads from Hugging Face Hub are disabled by default. The model weights are public/open models, but downloads still require an internet connection. Download the model files to the local cache as a one-time setup, or explicitly enable download with `TRIAGE_ALLOW_MODEL_DOWNLOAD=true`. The same setting applies to the embedding model (`all-MiniLM-L6-v2`) and DistilBERT. Once cached, set the variable back to `false` or leave it unset; all inference stays local.

The classical TF-IDF + calibrated LinearSVC severity baseline is fully local and does not need a pretrained model download. FAISS is also used locally for nearest-neighbor search.

`local_files_only` is used for model loading unless download is explicitly enabled. See the [Sentence Transformers loading options](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html) and [Transformers model loading options](https://huggingface.co/docs/transformers/main_classes/model) for this local-only behavior.

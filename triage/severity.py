"""Four-class severity prediction using calibrated TF-IDF or fine-tuned DistilBERT."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import numpy as np

SEVERITY_CLASSES = ("Low", "Medium", "High", "Critical")
Prediction = dict[str, float | str]


def softmax_probabilities(logits: list[float] | np.ndarray) -> np.ndarray:
    """Numerically stable softmax used by transformer inference and unit examples."""
    values = np.asarray(logits, dtype=np.float64)
    shifted = values - np.max(values)
    exp_values = np.exp(shifted)
    return exp_values / exp_values.sum()


class _TextDataset:
    """Tiny torch Dataset adapter, avoiding an extra `datasets` dependency."""

    def __init__(self, texts: list[str], labels: list[int], tokenizer: Any) -> None:
        self.encodings = tokenizer(texts, truncation=True, padding=True, max_length=256)
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> dict[str, Any]:
        import torch
        item = {key: torch.tensor(values[index]) for key, values in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[index], dtype=torch.long)
        return item


class SeverityClassifier:
    """Train either the explainable baseline or the requested transformer model."""

    def __init__(
        self,
        strategy: Literal["baseline", "transformer"] = "baseline",
        model_name: str = "distilbert-base-uncased",
        model_path: str | None = None,
        allow_remote_download: bool | None = None,
    ) -> None:
        if strategy not in ("baseline", "transformer"):
            raise ValueError("strategy must be 'baseline' or 'transformer'")
        self.strategy = strategy
        self.model_name = model_name
        self.model_path = model_path
        self.allow_remote_download = (
            os.getenv("TRIAGE_ALLOW_MODEL_DOWNLOAD", "false").lower() in {"1", "true", "yes"}
            if allow_remote_download is None else allow_remote_download
        )
        self._baseline = None
        self._tokenizer = None
        self._model = None

    @staticmethod
    def _validate_training_data(texts: list[str], labels: list[str]) -> list[int]:
        if len(texts) != len(labels) or not texts:
            raise ValueError("texts and labels must be non-empty lists of equal length")
        unknown = set(labels) - set(SEVERITY_CLASSES)
        if unknown:
            raise ValueError(f"Unknown severity labels: {sorted(unknown)}")
        missing = set(SEVERITY_CLASSES) - set(labels)
        if missing:
            raise ValueError(f"Training data must include all four classes: {sorted(missing)}")
        return [SEVERITY_CLASSES.index(label) for label in labels]

    def fit_baseline(self, texts: list[str], labels: list[str]) -> "SeverityClassifier":
        """Fit TF-IDF + LinearSVC calibrated with Platt's sigmoid method."""
        self._validate_training_data(texts, labels)
        too_small = [label for label in SEVERITY_CLASSES if labels.count(label) < 3]
        if too_small:
            raise ValueError(
                "Platt calibration with cv=3 needs at least three examples per class; "
                f"insufficient classes: {too_small}"
            )
        try:
            from sklearn.calibration import CalibratedClassifierCV
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.pipeline import make_pipeline
            from sklearn.svm import LinearSVC
        except ImportError as exc:
            raise RuntimeError("Install triage/requirements.txt to train the baseline") from exc
        # Three folds keep the classroom baseline usable with small balanced examples.
        self._baseline = CalibratedClassifierCV(
            estimator=make_pipeline(TfidfVectorizer(ngram_range=(1, 2), max_features=30_000),
                                    LinearSVC()),
            method="sigmoid",
            cv=3,
        )
        self._baseline.fit(texts, labels)
        self.strategy = "baseline"
        return self

    def fine_tune_transformer(
        self,
        texts: list[str],
        labels: list[str],
        output_dir: str | Path,
        epochs: int = 2,
        batch_size: int = 8,
        seed: int = 42,
    ) -> "SeverityClassifier":
        """Fine-tune DistilBERT with HuggingFace Trainer and a four-label head."""
        label_ids = self._validate_training_data(texts, labels)
        try:
            from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                                      Trainer, TrainingArguments)
        except ImportError as exc:
            raise RuntimeError("Install triage/requirements.txt to fine-tune DistilBERT") from exc
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, local_files_only=not self.allow_remote_download
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            num_labels=len(SEVERITY_CLASSES),
            id2label=dict(enumerate(SEVERITY_CLASSES)),
            label2id={name: index for index, name in enumerate(SEVERITY_CLASSES)},
            local_files_only=not self.allow_remote_download,
        )
        dataset = _TextDataset(texts, label_ids, self._tokenizer)
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            seed=seed,
            report_to="none",
            save_strategy="no",
            logging_strategy="no",
        )
        trainer = Trainer(model=self._model, args=training_args, train_dataset=dataset)
        trainer.train()
        trainer.save_model(str(output_dir))
        self._tokenizer.save_pretrained(str(output_dir))
        self.model_path = str(output_dir)
        self.strategy = "transformer"
        return self

    def _load_transformer(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        model_source = self.model_path or self.model_name
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Install triage/requirements.txt to use DistilBERT") from exc
        local_files_only = not self.allow_remote_download
        self._tokenizer = AutoTokenizer.from_pretrained(
            model_source, local_files_only=local_files_only
        )
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model_source, local_files_only=local_files_only
        )
        self._model.to("cuda" if torch.cuda.is_available() else "cpu")
        self._model.eval()

    def predict(self, text: str) -> Prediction:
        """Return all class probabilities, the argmax class, and its confidence."""
        if self.strategy == "baseline":
            if self._baseline is None:
                raise RuntimeError("Call fit_baseline before predicting with the baseline")
            raw = self._baseline.predict_proba([text])[0]
            probs = {label: float(raw[list(self._baseline.classes_).index(label)])
                     if label in self._baseline.classes_ else 0.0
                     for label in SEVERITY_CLASSES}
        else:
            self._load_transformer()
            import torch
            device = next(self._model.parameters()).device
            inputs = self._tokenizer(text, return_tensors="pt", truncation=True,
                                     padding=True, max_length=256).to(device)
            self._model.eval()
            with torch.no_grad():
                logits = self._model(**inputs).logits[0].detach().cpu().numpy()
            probabilities = softmax_probabilities(logits)
            probs = {label: float(probabilities[index])
                     for index, label in enumerate(SEVERITY_CLASSES)}
        predicted = max(SEVERITY_CLASSES, key=probs.__getitem__)
        return {**probs, "predicted_class": predicted, "confidence": probs[predicted]}

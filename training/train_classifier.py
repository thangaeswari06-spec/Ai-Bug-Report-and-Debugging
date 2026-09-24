"""
train_classifier.py  (DAY 1 deliverable)
-----------------------------------------
Fine-tunes CodeBERT (microsoft/codebert-base) as a 10-class bug-type
classifier using the "code + error" text as input.

Input  : data/bugs.csv
Output : models/bug_classifier/  (saved HF model + tokenizer + label map)

Usage:
    python training/train_classifier.py --epochs 5 --batch_size 8

NOTE: This script downloads the pretrained "microsoft/codebert-base"
weights from the Hugging Face Hub the first time it runs, so you need
internet access to huggingface.co on the machine where you train.
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)

MODEL_NAME = "microsoft/codebert-base"
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bugs.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "bug_classifier")
MAX_LEN = 256


class BugDataset(Dataset):
    """Wraps tokenized (code + error) text and integer labels for the Trainer API."""

    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


def build_input_text(row):
    """Combine language, code and error message into one string for the encoder."""
    stack = f"\nStack trace: {row['stack_trace']}" if isinstance(row["stack_trace"], str) and row["stack_trace"].strip() else ""
    return (
        f"Language: {row['language']}\n"
        f"Code:\n{row['code']}\n"
        f"Error: {row['error']}{stack}"
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    acc = accuracy_score(labels, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="macro", zero_division=0)
    return {"accuracy": acc, "precision_macro": precision, "recall_macro": recall, "f1_macro": f1}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    # ---- 1. Load + clean dataset -------------------------------------------------
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["code", "error", "bug_type"]).drop_duplicates(subset=["code", "error", "bug_type"])
    df["stack_trace"] = df["stack_trace"].fillna("")
    df["language"] = df["language"].str.lower().str.strip()

    labels_sorted = sorted(df["bug_type"].unique())
    label2id = {label: i for i, label in enumerate(labels_sorted)}
    id2label = {i: label for label, i in label2id.items()}
    df["label_id"] = df["bug_type"].map(label2id)

    texts = df.apply(build_input_text, axis=1).tolist()
    labels = df["label_id"].tolist()

    # ---- 2. Train / validation / test split (70 / 15 / 15) ------------------------
    train_texts, temp_texts, train_labels, temp_labels = train_test_split(
        texts, labels, test_size=0.30, random_state=42, stratify=labels
    )
    val_texts, test_texts, val_labels, test_labels = train_test_split(
        temp_texts, temp_labels, test_size=0.50, random_state=42, stratify=temp_labels
    )

    print(f"Train: {len(train_texts)}  Val: {len(val_texts)}  Test: {len(test_texts)}")

    # ---- 3. Tokenize ---------------------------------------------------------------
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    def tokenize(batch_texts):
        return tokenizer(batch_texts, truncation=True, padding="max_length", max_length=MAX_LEN)

    train_encodings = tokenize(train_texts)
    val_encodings = tokenize(val_texts)
    test_encodings = tokenize(test_texts)

    train_dataset = BugDataset(train_encodings, train_labels)
    val_dataset = BugDataset(val_encodings, val_labels)
    test_dataset = BugDataset(test_encodings, test_labels)

    # ---- 4. Load model ---------------------------------------------------------
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(labels_sorted),
        id2label=id2label,
        label2id=label2id,
    )

    # ---- 5. Train ----------------------------------------------------------------
    training_args = TrainingArguments(
        output_dir=os.path.join(OUTPUT_DIR, "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        logging_steps=10,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    # ---- 6. Evaluate on held-out test set ------------------------------------------
    test_results = trainer.evaluate(test_dataset)
    print("Test set results:", test_results)

    preds_output = trainer.predict(test_dataset)
    preds = np.argmax(preds_output.predictions, axis=1)
    cm = confusion_matrix(test_labels, preds)
    print("Confusion matrix (rows=true, cols=pred):")
    print(labels_sorted)
    print(cm)

    # ---- 7. Save model + tokenizer + label map -------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    with open(os.path.join(OUTPUT_DIR, "label_map.json"), "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f, indent=2)
    with open(os.path.join(OUTPUT_DIR, "test_metrics.json"), "w") as f:
        json.dump(test_results, f, indent=2)

    print(f"Saved fine-tuned classifier to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

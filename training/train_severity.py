"""
train_severity.py  (DAY 2 deliverable)
-----------------------------------------
Trains a severity classifier (LOW / MEDIUM / HIGH / CRITICAL) on top of
features derived from: predicted bug type + code/error/stack-trace signals.

Input  : data/bugs.csv
Output : models/severity_model/severity_model.joblib
         models/severity_model/label_encoder.joblib
         models/severity_model/metrics.json
         models/severity_model/confusion_matrix.png

Usage:
    python training/train_severity.py --model rf       # Random Forest (default)
    python training/train_severity.py --model xgb      # XGBoost
"""

import argparse
import json
import os

import joblib
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless-safe backend
import matplotlib.pyplot as plt
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)

from severity_features import extract_features, FEATURE_COLUMNS

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bugs.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "severity_model")
SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def load_dataset():
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["bug_type", "severity"])
    df["stack_trace"] = df["stack_trace"].fillna("")
    df["error"] = df["error"].fillna("")
    df["code"] = df["code"].fillna("")
    return df


def build_feature_matrix(df: pd.DataFrame):
    rows = []
    for _, r in df.iterrows():
        rows.append(extract_features(r["bug_type"], r["code"], r["error"], r["stack_trace"]))
    X = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    return X


def get_model(name: str):
    if name == "xgb":
        try:
            from xgboost import XGBClassifier
        except ImportError as e:
            raise SystemExit(
                "xgboost is not installed. Run: pip install xgboost --break-system-packages"
            ) from e
        return XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            random_state=42,
            eval_metric="mlogloss",
        )
    # Default: Random Forest
    return RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        random_state=42,
        class_weight="balanced",
    )


def plot_confusion_matrix(cm, labels, out_path):
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Severity Confusion Matrix")
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["rf", "xgb"], default="rf")
    parser.add_argument("--test_size", type=float, default=0.2)
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- 1. Load data + build features -----------------------------------------
    df = load_dataset()
    X = build_feature_matrix(df)
    y_raw = df["severity"].str.upper().tolist()

    encoder = LabelEncoder()
    encoder.classes_ = np.array(SEVERITY_ORDER)  # fix a consistent label order
    y = encoder.transform(y_raw)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42, stratify=y
    )
    print(f"Train size: {len(X_train)}  Test size: {len(X_test)}")

    # ---- 2. Train ------------------------------------------------------------------
    model = get_model(args.model)
    model.fit(X_train, y_train)

    # ---- 3. Evaluate --------------------------------------------------------------
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="macro", zero_division=0
    )
    report = classification_report(
        y_test, y_pred, target_names=SEVERITY_ORDER, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred, labels=list(range(len(SEVERITY_ORDER))))

    print(f"Accuracy: {acc:.4f}")
    print(f"Macro F1: {f1:.4f}")
    print(report)
    print("Confusion matrix:")
    print(SEVERITY_ORDER)
    print(cm)

    # ---- 4. Feature importance (sanity check) --------------------------------------
    if hasattr(model, "feature_importances_"):
        importances = sorted(
            zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda x: -x[1]
        )[:10]
        print("Top 10 important features:")
        for name, imp in importances:
            print(f"  {name}: {imp:.4f}")

    plot_confusion_matrix(cm, SEVERITY_ORDER, os.path.join(OUTPUT_DIR, "confusion_matrix.png"))

    # ---- 5. Save model + encoder + metrics ------------------------------------------
    joblib.dump(model, os.path.join(OUTPUT_DIR, "severity_model.joblib"))
    joblib.dump(encoder, os.path.join(OUTPUT_DIR, "label_encoder.joblib"))

    metrics = {
        "model_type": args.model,
        "accuracy": acc,
        "precision_macro": precision,
        "recall_macro": recall,
        "f1_macro": f1,
        "severity_order": SEVERITY_ORDER,
        "confusion_matrix": cm.tolist(),
        "train_size": len(X_train),
        "test_size": len(X_test),
    }
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved severity model + metrics to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

"""
Component 5: distilBERT Classifier Training Script
Architecture doc Sections 8.1–8.5.

Training data: OSHA IMIS petroleum sector corpus.
Input encoding: structured token sequence (Architecture doc Section 8.2).
Task: Multi-label — SIF category (6 classes) + severity (4 classes).
Target: ≥ 82% F1, maximize CRITICAL severity recall.
Save to: backend/models/distilbert-sif-v1.0/

Usage:
  cd classifier_training
  python train.py --data_dir ./data --output_dir ../backend/models/distilbert-sif-v1.0
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional

import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
from transformers import (
    DistilBertTokenizer,
    DistilBertForSequenceClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
)
from sklearn.metrics import f1_score, classification_report
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Label definitions
# ---------------------------------------------------------------------------

SIF_CATEGORIES = [
    "FALL_FROM_HEIGHT",
    "CAUGHT_IN_STRUCK_BY",
    "EXPLOSION_FIRE",
    "CHEMICAL_EXPOSURE",
    "ELECTRICAL",
    "VEHICLE_TRANSPORT",
]
SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Combined labels: category|severity (24 combinations)
COMBINED_LABELS = [f"{cat}|{sev}" for cat in SIF_CATEGORIES for sev in SEVERITIES]
LABEL2ID = {lbl: i for i, lbl in enumerate(COMBINED_LABELS)}
ID2LABEL = {i: lbl for lbl, i in LABEL2ID.items()}

NUM_LABELS = len(COMBINED_LABELS)  # 24


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class SIFDataset(Dataset):
    """
    Expects data as JSONL where each line is:
    {
      "subtype_id": "CE.01",
      "contributing_factors": ["PPE_FAILURE"],
      "equipment_classes": ["CHEMICAL_DRUM"],
      "activity_contexts": ["CHEMICAL_HANDLING"],
      "evidence_span": "operator not wearing gloves",
      "sif_category": "CHEMICAL_EXPOSURE",
      "severity": "HIGH"
    }
    """

    def __init__(self, data: list[dict], tokenizer, max_length: int = 256):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def _encode_input(self, item: dict) -> str:
        """Architecture doc Section 8.2 encoding."""
        return (
            f"SUBTYPE: {item.get('subtype_id', '')} "
            f"FACTORS: {' '.join(item.get('contributing_factors', []))} "
            f"EQUIPMENT: {' '.join(item.get('equipment_classes', []))} "
            f"ACTIVITY: {' '.join(item.get('activity_contexts', []))} "
            f"EVIDENCE: {item.get('evidence_span', '')}"
        )

    def __getitem__(self, idx):
        item = self.data[idx]
        text  = self._encode_input(item)
        label_key = f"{item['sif_category']}|{item['severity']}"
        label_id  = LABEL2ID.get(label_key, 0)

        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids":      encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels":         torch.tensor(label_id, dtype=torch.long),
        }


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_data(data_dir: str) -> list[dict]:
    """Load all JSONL files from data_dir."""
    data_path = Path(data_dir)
    records = []

    # Try JSONL first
    for jsonl_file in data_path.glob("*.jsonl"):
        with open(jsonl_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        logger.info(f"Loaded {len(records)} records from {jsonl_file}")

    # Try JSON arrays
    for json_file in data_path.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)
        if isinstance(data, list):
            records.extend(data)
            logger.info(f"Loaded {len(data)} records from {json_file}")

    if not records:
        logger.warning(f"No data found in {data_dir} — generating synthetic training data")
        records = _generate_synthetic_data()

    logger.info(f"Total training records: {len(records)}")
    return records


def _generate_synthetic_data() -> list[dict]:
    """
    Generate minimal synthetic training data when OSHA corpus is not available.
    For demonstration only — not sufficient for production accuracy.
    """
    templates = [
        # Chemical Exposure
        {"subtype_id": "CE.01", "contributing_factors": ["PPE_FAILURE"],
         "equipment_classes": ["CHEMICAL_DRUM"], "activity_contexts": ["CHEMICAL_HANDLING"],
         "evidence_span": "operator not wearing gloves during chemical transfer",
         "sif_category": "CHEMICAL_EXPOSURE", "severity": "HIGH"},
        {"subtype_id": "CE.02", "contributing_factors": ["EQUIPMENT_FAULT", "PPE_FAILURE"],
         "equipment_classes": ["H2S_MONITOR"], "activity_contexts": ["OPERATION"],
         "evidence_span": "H2S alarm sounded, worker near well head without SCBA",
         "sif_category": "CHEMICAL_EXPOSURE", "severity": "CRITICAL"},
        {"subtype_id": "CE.01", "contributing_factors": ["PROCEDURE_VIOLATION"],
         "equipment_classes": ["REAGENT_TANK"], "activity_contexts": ["SAMPLING"],
         "evidence_span": "acid sampling conducted without face shield",
         "sif_category": "CHEMICAL_EXPOSURE", "severity": "MEDIUM"},
        # Fall from Height
        {"subtype_id": "FFH.01", "contributing_factors": ["PPE_FAILURE"],
         "equipment_classes": ["SCAFFOLD"], "activity_contexts": ["MAINTENANCE"],
         "evidence_span": "worker observed on scaffold without harness at 6m elevation",
         "sif_category": "FALL_FROM_HEIGHT", "severity": "HIGH"},
        {"subtype_id": "FFH.02", "contributing_factors": ["EQUIPMENT_FAULT"],
         "equipment_classes": ["LADDER"], "activity_contexts": ["INSPECTION"],
         "evidence_span": "ladder foot slipped on wet surface, worker caught themselves",
         "sif_category": "FALL_FROM_HEIGHT", "severity": "MEDIUM"},
        # Explosion/Fire
        {"subtype_id": "EF.01", "contributing_factors": ["EQUIPMENT_FAULT"],
         "equipment_classes": ["PIPELINE"], "activity_contexts": ["OPERATION"],
         "evidence_span": "hydrocarbon vapour detected near flange, ignition source present",
         "sif_category": "EXPLOSION_FIRE", "severity": "CRITICAL"},
        {"subtype_id": "EF.04", "contributing_factors": ["PROCEDURE_VIOLATION"],
         "equipment_classes": ["STORAGE_TANK"], "activity_contexts": ["STARTUP"],
         "evidence_span": "tank pressure relief valve opened, gas cloud formed near ignition sources",
         "sif_category": "EXPLOSION_FIRE", "severity": "HIGH"},
        # Electrical
        {"subtype_id": "ELEC.03", "contributing_factors": ["PROCEDURE_VIOLATION"],
         "equipment_classes": ["LOCKOUT_DEVICE"], "activity_contexts": ["MAINTENANCE"],
         "evidence_span": "pump restarted while technician still working on impeller, LOTO not applied",
         "sif_category": "ELECTRICAL", "severity": "CRITICAL"},
        {"subtype_id": "ELEC.01", "contributing_factors": ["PPE_FAILURE", "PROCEDURE_VIOLATION"],
         "equipment_classes": ["ELECTRICAL_PANEL"], "activity_contexts": ["ELECTRICAL_WORK"],
         "evidence_span": "electrician contacted live terminal without insulated gloves",
         "sif_category": "ELECTRICAL", "severity": "HIGH"},
        # Vehicle/Transport
        {"subtype_id": "VT.01", "contributing_factors": ["PROCEDURE_VIOLATION"],
         "equipment_classes": ["TANKER"], "activity_contexts": ["TRANSPORT"],
         "evidence_span": "tanker took corner too fast, near rollover on site road",
         "sif_category": "VEHICLE_TRANSPORT", "severity": "HIGH"},
        # Caught In/Struck By
        {"subtype_id": "CISB.01", "contributing_factors": ["PROCEDURE_VIOLATION"],
         "equipment_classes": ["PUMP"], "activity_contexts": ["MAINTENANCE"],
         "evidence_span": "coupling guard removed for inspection, shaft still rotating",
         "sif_category": "CAUGHT_IN_STRUCK_BY", "severity": "HIGH"},
        {"subtype_id": "CISB.02", "contributing_factors": ["PPE_FAILURE"],
         "equipment_classes": ["TOOL"], "activity_contexts": ["CONSTRUCTION"],
         "evidence_span": "wrench dropped from elevated work area, nearly struck worker below",
         "sif_category": "CAUGHT_IN_STRUCK_BY", "severity": "MEDIUM"},
    ]

    # Augment to reach training-viable size
    augmented = []
    for _ in range(50):  # 50× augmentation
        augmented.extend(templates)
    return augmented


# ---------------------------------------------------------------------------
# Compute metrics
# ---------------------------------------------------------------------------

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    f1 = f1_score(labels, predictions, average="weighted", zero_division=0)

    # CRITICAL severity recall
    critical_indices = [i for lbl, i in LABEL2ID.items() if "CRITICAL" in lbl]
    critical_mask = np.isin(labels, critical_indices)
    if critical_mask.sum() > 0:
        pred_critical = np.isin(predictions, critical_indices)
        critical_recall = (critical_mask & pred_critical).sum() / critical_mask.sum()
    else:
        critical_recall = 0.0

    return {
        "f1_weighted":      f1,
        "critical_recall":  critical_recall,
    }


# ---------------------------------------------------------------------------
# Main training
# ---------------------------------------------------------------------------

def train(data_dir: str, output_dir: str, epochs: int = 5, batch_size: int = 16):
    logger.info("=== SIF Classifier Training ===")

    # Load data
    all_data = load_data(data_dir)
    train_data, eval_data = train_test_split(all_data, test_size=0.15, random_state=42)
    logger.info(f"Train: {len(train_data)} | Eval: {len(eval_data)}")

    # Tokenizer and model
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    model = DistilBertForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    # Datasets
    train_dataset = SIFDataset(train_data, tokenizer)
    eval_dataset  = SIFDataset(eval_data, tokenizer)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir=f"{output_dir}/logs",
        logging_steps=10,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_weighted",
        greater_is_better=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    trainer.train()

    # Save model
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    logger.info(f"Model saved to {output_dir}")

    # Final evaluation
    results = trainer.evaluate()
    logger.info(f"Final eval: F1={results.get('eval_f1_weighted', 0):.3f}, "
                f"CRITICAL recall={results.get('eval_critical_recall', 0):.3f}")

    if results.get("eval_f1_weighted", 0) < 0.82:
        logger.warning(
            f"F1 {results['eval_f1_weighted']:.3f} < 0.82 target. "
            "Consider adding more OSHA petroleum sector training data."
        )

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir",   default="./data",
                        help="Directory containing JSONL training data")
    parser.add_argument("--output_dir", default="../backend/models/distilbert-sif-v1.0",
                        help="Where to save the trained model")
    parser.add_argument("--epochs",     type=int, default=5)
    parser.add_argument("--batch_size", type=int, default=16)
    args = parser.parse_args()

    train(args.data_dir, args.output_dir, args.epochs, args.batch_size)

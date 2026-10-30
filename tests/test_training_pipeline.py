import hashlib
from pathlib import Path

import pytest
import torch

from train import balanced_class_weights, compute_metrics, load_checkpoint, select_rejection_threshold, validate_dataset_contract
from data_pipeline import copy_sample


def _touch(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_dataset_contract_requires_registered_order_and_unknown_last(tmp_path):
    ids = [f"{i:04d}" for i in range(50)]
    for split in ("train", "val"):
        for cid in ids + ["unknown"]:
            _touch(tmp_path / split / cid / f"{split}-{cid}.jpg", f"{split}-{cid}".encode())

    summary = validate_dataset_contract(tmp_path, ids)

    assert summary["classes"] == ids + ["unknown"]
    assert summary["train_images"] == 51
    assert summary["val_images"] == 51


def test_dataset_contract_rejects_duplicate_content_across_splits(tmp_path):
    ids = [f"{i:04d}" for i in range(50)]
    for split in ("train", "val"):
        for cid in ids + ["unknown"]:
            payload = b"same" if cid == "0000" else f"{split}-{cid}".encode()
            _touch(tmp_path / split / cid / f"{split}-{cid}.jpg", payload)

    with pytest.raises(ValueError, match="overlap"):
        validate_dataset_contract(tmp_path, ids)


def test_balanced_weights_downweight_larger_unknown_class():
    targets = [0, 0, 1, 1, 1, 1]
    weights = balanced_class_weights(targets, num_classes=2)

    assert torch.isclose(weights[0], torch.tensor(1.5))
    assert torch.isclose(weights[1], torch.tensor(0.75))


def test_compute_metrics_reports_all_taskbook_measures():
    metrics = compute_metrics([0, 0, 1, 1, 2, 2], [0, 1, 1, 1, 2, 0], 3)

    assert set(metrics) >= {
        "accuracy", "macro_precision", "macro_recall", "macro_f1",
        "unknown_recall", "known_rejection_rate", "confusion_matrix",
        "per_class_precision", "per_class_recall", "per_class_f1",
    }
    assert len(metrics["confusion_matrix"]) == 3
    assert metrics["unknown_recall"] == pytest.approx(0.5)
    assert metrics["known_rejection_rate"] == pytest.approx(0.0)


def test_copy_sample_excludes_content_seen_in_other_split(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    _touch(src / "duplicate.jpg", b"duplicate")
    _touch(src / "unique.jpg", b"unique")
    excluded = {hashlib.sha256(b"duplicate").digest()}

    copied, hashes = copy_sample(src, dst, limit=2, seed=1, excluded_hashes=excluded)

    assert copied == 1
    assert [p.name for p in dst.iterdir()] == ["unique.jpg"]
    assert hashes == {hashlib.sha256(b"unique").digest()}


def test_load_checkpoint_accepts_locally_created_training_metadata(tmp_path):
    path = tmp_path / "model.pt"
    torch.save({"model": {}, "training_config": {"torch": torch.__version__}}, path)

    loaded = load_checkpoint(path, map_location="cpu")

    assert str(loaded["training_config"]["torch"]) == str(torch.__version__)


def test_threshold_selection_uses_macro_f1_and_can_reject_low_confidence_prediction():
    probabilities = torch.tensor([
        [.90, .05, .05],
        [.05, .90, .05],
        [.45, .40, .15],
        [.10, .20, .70],
    ])
    result = select_rejection_threshold([0, 1, 2, 2], probabilities, [0.0, 0.5])

    assert result["threshold"] == 0.5
    assert result["macro_f1"] == pytest.approx(1.0)


def test_batch_prediction_uses_shared_classifier_and_threshold(tmp_path, monkeypatch):
    import csv
    import agent_tools
    from train import predict

    class Classifier:
        def __init__(self, checkpoint):
            pass

        def classify_car(self, image):
            return {"label": "unknown", "confidence": 0.21}

    monkeypatch.setattr(agent_tools, "VehicleClassifier", Classifier)
    _touch(tmp_path / "images" / "nested" / "a.jpg", b"image")
    target = tmp_path / "result" / "predictions.csv"
    predict("test.pt", tmp_path / "images", target)
    with target.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows == [{"image_id": "a.jpg", "predicted_label": "unknown", "confidence": "0.21"}]


def test_batch_prediction_rejects_empty_or_duplicate_image_ids(tmp_path):
    from train import predict
    with pytest.raises(ValueError, match="没有"):
        predict("unused.pt", tmp_path, tmp_path / "out.csv")
    _touch(tmp_path / "a" / "same.jpg", b"one")
    _touch(tmp_path / "b" / "same.jpg", b"two")
    with pytest.raises(ValueError, match="重名"):
        predict("unused.pt", tmp_path, tmp_path / "out.csv")

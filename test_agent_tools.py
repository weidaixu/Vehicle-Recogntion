from io import BytesIO
from pathlib import Path

from agent_tools import VehicleClassifier


def test_classifier_accepts_file_like_upload():
    image_path = next(Path("prepared_final/val").glob("*/*.jpg"))
    uploaded_like = BytesIO(image_path.read_bytes())
    classifier = VehicleClassifier("output/model.pt")
    result = classifier.classify_car(uploaded_like)
    assert result["ok"] is True
    assert 0 <= result["confidence"] <= 1
    assert len(result["top_k"]) == 3


def test_classifier_uses_validation_calibrated_threshold_by_default():
    classifier = VehicleClassifier("output/model.pt")
    image_path = next(Path("prepared_final/val").glob("*/*.jpg"))

    result = classifier.classify_car(BytesIO(image_path.read_bytes()))

    assert classifier.threshold == 0.26
    assert result["threshold"] == classifier.threshold

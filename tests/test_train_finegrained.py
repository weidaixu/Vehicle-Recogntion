import numpy as np
import torch
from torch import nn

from train_finegrained import aggregate_to_submission_logits, load_initial_weights


def test_aggregate_to_submission_logits_keeps_known_columns_and_maxes_unknown_sources():
    source_classes = ["0000", "0001", "0002", "0003"]
    known_classes = ["0000", "0002"]
    logits = np.asarray([[1.0, 5.0, 3.0, 4.0]], dtype=np.float32)

    aggregated = aggregate_to_submission_logits(logits, source_classes, known_classes)

    np.testing.assert_array_equal(
        aggregated,
        np.asarray([[1.0, 3.0, 5.0]], dtype=np.float32),
    )


class TinyClassifier(nn.Module):
    def __init__(self, classes: int):
        super().__init__()
        self.backbone = nn.Linear(2, 2)
        self.fc = nn.Linear(2, classes)


def test_load_initial_weights_resumes_full_checkpoint_when_classes_match():
    model = TinyClassifier(3)
    checkpoint_model = TinyClassifier(3)
    with torch.no_grad():
        checkpoint_model.backbone.weight.fill_(2.0)
        checkpoint_model.fc.weight.fill_(3.0)
    checkpoint = {
        "model": checkpoint_model.state_dict(),
        "classes": ["a", "b", "c"],
    }

    mode = load_initial_weights(model, checkpoint, ["a", "b", "c"])

    assert mode == "resume"
    torch.testing.assert_close(model.backbone.weight, torch.full_like(model.backbone.weight, 2.0))
    torch.testing.assert_close(model.fc.weight, torch.full_like(model.fc.weight, 3.0))


def test_load_initial_weights_uses_only_backbone_when_classes_differ():
    model = TinyClassifier(3)
    original_head = model.fc.weight.detach().clone()
    checkpoint_model = TinyClassifier(2)
    with torch.no_grad():
        checkpoint_model.backbone.weight.fill_(4.0)
        checkpoint_model.fc.weight.fill_(5.0)
    checkpoint = {
        "model": checkpoint_model.state_dict(),
        "classes": ["old-a", "old-b"],
    }

    mode = load_initial_weights(model, checkpoint, ["a", "b", "c"])

    assert mode == "backbone"
    torch.testing.assert_close(model.backbone.weight, torch.full_like(model.backbone.weight, 4.0))
    torch.testing.assert_close(model.fc.weight, original_head)

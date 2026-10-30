import csv

import numpy as np

from generate_submission import (
    adapt_checkpoint_logits,
    align_logits_with_labels,
    balanced_source_prior_labels,
    finalize_submission_predictions,
    labels_from_logits,
    write_submission,
)


def test_labels_from_logits_applies_unknown_class_and_rejection_threshold():
    classes = ["0000", "0001", "unknown"]
    logits = np.asarray(
        [
            [4.0, 0.0, -1.0],
            [0.2, 0.1, 0.0],
            [0.0, 0.0, 3.0],
        ],
        dtype=np.float32,
    )

    assert labels_from_logits(logits, classes, threshold=0.60) == [
        "0000",
        "unknown",
        "unknown",
    ]


def test_labels_from_logits_supports_shrunk_per_class_thresholds():
    classes = ["0000", "0001", "unknown"]
    logits = np.asarray([[0.2, 0.1, 0.0], [0.1, 0.2, 0.0]], dtype=np.float32)

    assert labels_from_logits(
        logits,
        classes,
        threshold=0.60,
        class_thresholds=np.asarray([0.30, 0.80]),
        threshold_shrink=1.0,
    ) == ["0000", "unknown"]


def test_align_logits_makes_npz_argmax_match_final_csv_labels_without_mutating_input():
    classes = ["0000", "0001", "unknown"]
    logits = np.asarray([[2.0, 1.0, 0.0], [0.0, 1.0, 2.0]], dtype=np.float32)
    original = logits.copy()

    aligned = align_logits_with_labels(logits, ["unknown", "unknown"], classes)

    assert aligned.argmax(axis=1).tolist() == [2, 2]
    np.testing.assert_array_equal(logits, original)


def test_adapt_checkpoint_logits_aggregates_finegrained_unknown_with_offset():
    logits = np.asarray([[1.0, 5.0, 3.0, 4.0]], dtype=np.float32)

    adapted = adapt_checkpoint_logits(
        logits,
        checkpoint_classes=["0000", "0001", "0002", "0003"],
        known_classes=["0000", "0002"],
        unknown_logit_offset=-0.75,
    )

    np.testing.assert_array_equal(
        adapted,
        np.asarray([[1.0, 3.0, 4.25]], dtype=np.float32),
    )


def test_balanced_source_prior_labels_assigns_each_source_quota_once():
    source_classes = ["known-a", "known-b", "other-a", "other-b"]
    known_classes = ["known-a", "known-b"]
    logits = np.asarray(
        [
            [8.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 8.0, 1.0],
            [0.0, 8.0, 0.0, 1.0],
            [0.0, 0.0, 1.0, 8.0],
        ],
        dtype=np.float32,
    )

    labels = balanced_source_prior_labels(
        logits,
        source_classes,
        known_classes,
        samples_per_source=1,
        temperature=0.75,
    )

    assert labels == ["known-a", "unknown", "known-b", "unknown"]


def test_finalize_submission_predictions_uses_the_51_class_submission_label_space():
    logits = np.asarray([[1.0, 3.0, 4.25]], dtype=np.float32)

    labels, aligned = finalize_submission_predictions(
        logits,
        known_classes=["0000", "0002"],
        threshold=0.0,
        class_thresholds=np.asarray([0.0, 0.0], dtype=np.float32),
        threshold_shrink=1.0,
    )

    assert labels == ["unknown"]
    assert aligned.argmax(axis=1).tolist() == [2]


def test_write_submission_matches_edubench_file_contract(tmp_path):
    image_ids = np.asarray(["000001", "000002"], dtype="<U6")
    logits = np.asarray([[2.0, 1.0, 0.0], [0.0, 1.0, 2.0]], dtype=np.float32)
    known_classes = ["0000", "0001"]
    labels = ["0000", "unknown"]

    write_submission(tmp_path, image_ids, logits, known_classes, labels)

    classes_bytes = (tmp_path / "classes.txt").read_bytes()
    assert classes_bytes == b"0000\n0001\n"
    with (tmp_path / "result.csv").open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle)) == [
            ["image_id", "predicted_label"],
            ["000001", "0000"],
            ["000002", "unknown"],
        ]
    with np.load(tmp_path / "result.npz", allow_pickle=False) as archive:
        assert archive.files == ["image_id", "logits"]
        assert archive["image_id"].dtype.kind == "U"
        assert archive["image_id"].tolist() == ["000001", "000002"]
        assert archive["logits"].dtype == np.float32
        np.testing.assert_array_equal(archive["logits"], logits)

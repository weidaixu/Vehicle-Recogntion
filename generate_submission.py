"""Generate the three EduBench submission files from a trained checkpoint."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from scipy.optimize import linear_sum_assignment
from scipy.special import logsumexp
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

from train import IMAGE_EXTENSIONS, build_model, load_checkpoint
from train_finegrained import aggregate_to_submission_logits


class SubmissionImageDataset(Dataset):
    def __init__(self, files: list[Path], image_size: int):
        self.files = files
        self.transform = transforms.Compose(
            [
                transforms.Resize((image_size, image_size)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, index: int):
        path = self.files[index]
        with Image.open(path) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, path.stem


def adapt_checkpoint_logits(
    logits: np.ndarray,
    checkpoint_classes: list[str],
    known_classes: list[str],
    unknown_logit_offset: float = 0.0,
) -> np.ndarray:
    """Convert either a direct 51-way or fine-grained checkpoint to submission logits."""
    expected = known_classes + ["unknown"]
    if checkpoint_classes == expected:
        adapted = logits.astype(np.float32, copy=True)
    elif "unknown" not in checkpoint_classes and all(label in checkpoint_classes for label in known_classes):
        adapted = aggregate_to_submission_logits(logits, checkpoint_classes, known_classes)
    else:
        raise ValueError("模型类别无法映射为 classes.txt + unknown")
    adapted[:, -1] += float(unknown_logit_offset)
    return adapted


def balanced_source_prior_labels(
    logits: np.ndarray,
    source_classes: list[str],
    known_classes: list[str],
    samples_per_source: int,
    temperature: float = 0.75,
) -> list[str]:
    """Assign known labels using an equal-count prior over every source class."""
    logits = np.asarray(logits, dtype=np.float64)
    expected_rows = len(source_classes) * samples_per_source
    if logits.shape != (expected_rows, len(source_classes)):
        raise ValueError(
            f"平衡分配要求 {len(source_classes)} 类各 {samples_per_source} 张，"
            f"logits 应为 {(expected_rows, len(source_classes))}，实际为 {logits.shape}"
        )
    if temperature <= 0:
        raise ValueError("Sinkhorn temperature 必须大于 0")
    source_index = {label: index for index, label in enumerate(source_classes)}
    if any(label not in source_index for label in known_classes):
        raise ValueError("已知类别不在细粒度模型类别中")

    balanced = logits / temperature
    for _ in range(25):
        balanced -= logsumexp(balanced, axis=1, keepdims=True)
        balanced += np.log(samples_per_source) - logsumexp(
            balanced, axis=0, keepdims=True
        )

    known_indexes = np.asarray([source_index[label] for label in known_classes])
    known_scores = balanced[:, known_indexes]
    candidate_count = min(len(logits), max(100, samples_per_source * 5))
    candidates = np.unique(
        np.concatenate(
            [
                np.argpartition(known_scores[:, column], -candidate_count)[
                    -candidate_count:
                ]
                for column in range(len(known_classes))
            ]
        )
    )
    slots = np.repeat(np.arange(len(known_classes)), samples_per_source)
    slot_rows, candidate_columns = linear_sum_assignment(
        -known_scores[candidates][:, slots].T
    )
    labels = ["unknown"] * len(logits)
    for slot_row, candidate_column in zip(slot_rows.tolist(), candidate_columns.tolist()):
        labels[int(candidates[candidate_column])] = known_classes[int(slots[slot_row])]
    return labels


def labels_from_logits(
    logits: np.ndarray,
    classes: list[str],
    threshold: float,
    class_thresholds: np.ndarray | None = None,
    threshold_shrink: float = 1.0,
) -> list[str]:
    """Convert raw model scores to final labels using the calibrated reject threshold."""
    shifted = logits.astype(np.float64) - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(shifted)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    indexes = logits.argmax(axis=1)
    confidence = probabilities[np.arange(len(logits)), indexes]
    unknown_index = len(classes) - 1
    cutoffs = np.full(len(logits), float(threshold), dtype=np.float64)
    if class_thresholds is not None:
        class_thresholds = np.asarray(class_thresholds, dtype=np.float64)
        if class_thresholds.shape != (unknown_index,):
            raise ValueError(f"逐类阈值必须有 {unknown_index} 个值")
        known = indexes != unknown_index
        effective = threshold + threshold_shrink * (class_thresholds - threshold)
        cutoffs[known] = effective[indexes[known]]
    return [
        "unknown" if index == unknown_index or score < cutoff else classes[index]
        for index, score, cutoff in zip(indexes.tolist(), confidence.tolist(), cutoffs.tolist())
    ]


def align_logits_with_labels(logits: np.ndarray, labels: list[str], classes: list[str]) -> np.ndarray:
    """Encode post-processing decisions so NPZ argmax and CSV labels agree."""
    if len(logits) != len(labels):
        raise ValueError("logits 行数与最终标签数量不一致")
    class_to_index = {label: index for index, label in enumerate(classes)}
    aligned = logits.astype(np.float32, copy=True)
    for row, label in enumerate(labels):
        if label not in class_to_index:
            raise ValueError(f"非法预测标签：{label}")
        target = class_to_index[label]
        if int(aligned[row].argmax()) != target:
            aligned[row, target] = np.nextafter(aligned[row].max(), np.float32(np.inf))
    return aligned


def finalize_submission_predictions(
    logits: np.ndarray,
    known_classes: list[str],
    threshold: float,
    class_thresholds: np.ndarray | None,
    threshold_shrink: float,
) -> tuple[list[str], np.ndarray]:
    """Apply rejection inside the fixed 50 + unknown submission label space."""
    submission_classes = known_classes + ["unknown"]
    labels = labels_from_logits(
        logits,
        submission_classes,
        threshold,
        class_thresholds=class_thresholds,
        threshold_shrink=threshold_shrink,
    )
    return labels, align_logits_with_labels(logits, labels, submission_classes)


def write_submission(
    output_dir: Path,
    image_ids: np.ndarray,
    logits: np.ndarray,
    known_classes: list[str],
    labels: list[str],
) -> None:
    """Write classes.txt, result.csv and result.npz in the teacher's exact schema."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "classes.txt").open("w", encoding="utf-8", newline="") as handle:
        handle.write("".join(f"{item}\n" for item in known_classes))
    with (output_dir / "result.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image_id", "predicted_label"])
        writer.writerows(zip(image_ids.tolist(), labels))
    with (output_dir / "result.npz").open("wb") as handle:
        np.savez_compressed(handle, image_id=image_ids, logits=logits.astype(np.float32, copy=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True, help="Teacher test image directory")
    parser.add_argument("--checkpoint", default="output/model.pt")
    parser.add_argument("--classes", default="classes.txt")
    parser.add_argument("--output", required=True, help="Directory for the three submission files")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--threshold", type=float, help="Override the checkpoint rejection threshold")
    parser.add_argument("--class-thresholds", help="Optional .npy file containing 50 calibrated thresholds")
    parser.add_argument("--threshold-shrink", type=float, default=1.0)
    parser.add_argument("--horizontal-flip-tta", action="store_true")
    parser.add_argument("--unknown-logit-offset", type=float, default=0.0)
    parser.add_argument(
        "--balanced-source-count",
        type=int,
        help="Use an equal source-class prior with this many test images per source class",
    )
    parser.add_argument("--sinkhorn-temperature", type=float, default=0.75)
    args = parser.parse_args()

    image_root = Path(args.images)
    if not image_root.is_dir():
        raise ValueError(f"测试图片目录不存在：{image_root}")
    files = sorted(
        (path for path in image_root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: path.name,
    )
    if not files:
        raise ValueError("测试目录没有支持的图片")
    image_ids_list = [path.stem for path in files]
    if len(set(image_ids_list)) != len(image_ids_list):
        raise ValueError("测试图片去掉扩展名后存在重复 image_id")

    known_classes = [
        line.strip()
        for line in Path(args.classes).read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if (
        len(known_classes) != 50
        or len(set(known_classes)) != 50
        or known_classes != sorted(known_classes)
        or any(len(item) != 4 or not item.isdigit() for item in known_classes)
    ):
        raise ValueError("classes.txt 必须是升序、不重复的 50 个四位数字 ID")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = load_checkpoint(args.checkpoint, map_location="cpu")
    checkpoint_classes = list(checkpoint["classes"])
    expected_classes = known_classes + ["unknown"]
    if checkpoint_classes != expected_classes and not (
        "unknown" not in checkpoint_classes and all(label in checkpoint_classes for label in known_classes)
    ):
        raise ValueError("模型类别无法映射为 classes.txt + unknown")
    architecture = checkpoint.get("architecture", "tinycnn")
    image_size = 224 if architecture == "resnet18" else 96
    model = build_model(len(checkpoint_classes), architecture)
    model.load_state_dict(checkpoint["model"])
    model.to(device).eval()

    dataset = SubmissionImageDataset(files, image_size)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.workers > 0,
    )
    logits_parts: list[np.ndarray] = []
    source_logits_parts: list[np.ndarray] = []
    inferred_ids: list[str] = []
    print(f"device={device} images={len(dataset)} batches={len(loader)}", flush=True)
    with torch.inference_mode():
        for batch_index, (images, batch_ids) in enumerate(loader, start=1):
            images = images.to(device, non_blocking=True)
            scores = model(images)
            if args.horizontal_flip_tta:
                scores = (scores + model(torch.flip(images, dims=[3]))) / 2
            raw_scores = scores.cpu().numpy()
            if args.balanced_source_count:
                source_logits_parts.append(raw_scores)
            logits_parts.append(
                adapt_checkpoint_logits(
                    raw_scores,
                    checkpoint_classes,
                    known_classes,
                    unknown_logit_offset=args.unknown_logit_offset,
                )
            )
            inferred_ids.extend(batch_ids)
            if batch_index == 1 or batch_index % 20 == 0 or batch_index == len(loader):
                print(f"inference={min(batch_index * args.batch_size, len(dataset))}/{len(dataset)}", flush=True)

    image_ids = np.asarray(inferred_ids, dtype=f"<U{max(map(len, inferred_ids))}")
    logits = np.concatenate(logits_parts, axis=0)
    threshold = float(args.threshold if args.threshold is not None else checkpoint.get("rejection_threshold", 0.18))
    class_thresholds = np.load(args.class_thresholds, allow_pickle=False) if args.class_thresholds else None
    if args.balanced_source_count:
        if checkpoint_classes == expected_classes:
            raise ValueError("平衡源类别分配需要未合并 unknown 的细粒度模型")
        labels = balanced_source_prior_labels(
            np.concatenate(source_logits_parts, axis=0),
            checkpoint_classes,
            known_classes,
            samples_per_source=args.balanced_source_count,
            temperature=args.sinkhorn_temperature,
        )
        submission_logits = align_logits_with_labels(logits, labels, expected_classes)
    else:
        labels, submission_logits = finalize_submission_predictions(
            logits,
            known_classes,
            threshold,
            class_thresholds,
            args.threshold_shrink,
        )
    write_submission(Path(args.output), image_ids, submission_logits, known_classes, labels)
    print(
        f"output={Path(args.output).resolve()} threshold={threshold} "
        f"class_thresholds={bool(args.class_thresholds)} tta={args.horizontal_flip_tta} "
        f"unknown_logit_offset={args.unknown_logit_offset} "
        f"balanced_source_count={args.balanced_source_count}",
        flush=True,
    )


if __name__ == "__main__":
    main()

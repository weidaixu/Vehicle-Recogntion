"""Train an auxiliary 827-way classifier and aggregate it to 50 + unknown at submission time."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms


def aggregate_to_submission_logits(
    logits: np.ndarray, source_classes: list[str], known_classes: list[str]
) -> np.ndarray:
    """Keep the 50 registered columns and collapse all other source classes to unknown."""
    source_index = {label: index for index, label in enumerate(source_classes)}
    known_indexes = [source_index[label] for label in known_classes]
    unknown_indexes = [index for index, label in enumerate(source_classes) if label not in set(known_classes)]
    known_logits = logits[:, known_indexes]
    unknown_logits = logits[:, unknown_indexes].max(axis=1, keepdims=True)
    return np.concatenate([known_logits, unknown_logits], axis=1).astype(np.float32, copy=False)


def load_initial_weights(
    model: nn.Module, checkpoint: dict, dataset_classes: list[str]
) -> str:
    """Resume a matching classifier, otherwise transfer every non-head weight."""
    if list(checkpoint.get("classes", [])) == list(dataset_classes):
        model.load_state_dict(checkpoint["model"])
        return "resume"
    backbone = {
        key: value for key, value in checkpoint["model"].items() if not key.startswith("fc.")
    }
    missing, unexpected = model.load_state_dict(backbone, strict=False)
    if set(missing) != {"fc.weight", "fc.bias"} or unexpected:
        raise ValueError(f"骨干网络初始化不完整：missing={missing}, unexpected={unexpected}")
    return "backbone"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default=".")
    parser.add_argument(
        "--init",
        required=True,
        help="51-class backbone checkpoint or a matching 827-class checkpoint to resume",
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch", type=int, default=96)
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate for the new 827-way head")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260922)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    root = Path(args.data_root)
    image_size = 224
    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(image_size, scale=(0.72, 1.0), ratio=(0.8, 1.25)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(7),
            transforms.ColorJitter(0.2, 0.2, 0.2, 0.06),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    val_transform = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    train_dataset = datasets.ImageFolder(root / "train", transform=train_transform)
    val_dataset = datasets.ImageFolder(root / "val", transform=val_transform)
    if train_dataset.classes != val_dataset.classes or len(train_dataset.classes) != 827:
        raise ValueError("train/val 必须包含顺序一致的 827 个原始类别")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = models.resnet18(weights=None)
    model.fc = nn.Linear(model.fc.in_features, len(train_dataset.classes))
    initial = torch.load(args.init, map_location="cpu", weights_only=False)
    init_mode = load_initial_weights(model, initial, train_dataset.classes)
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.layer4.parameters():
        parameter.requires_grad = True
    for parameter in model.fc.parameters():
        parameter.requires_grad = True
    model.to(device)

    counts = torch.bincount(torch.as_tensor(train_dataset.targets), minlength=len(train_dataset.classes)).float()
    class_weights = len(train_dataset) / (len(train_dataset.classes) * counts)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights.to(device), label_smoothing=0.05)
    optimizer = torch.optim.AdamW(
        [
            {"params": model.layer4.parameters(), "lr": args.lr * 0.2},
            {"params": model.fc.parameters(), "lr": args.lr},
        ],
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs), eta_min=args.lr * 0.03)
    common = {
        "batch_size": args.batch,
        "num_workers": args.workers,
        "pin_memory": device.type == "cuda",
        "persistent_workers": args.workers > 0,
    }
    train_loader = DataLoader(train_dataset, shuffle=True, **common)
    val_loader = DataLoader(val_dataset, shuffle=False, **common)
    experiment_dir = Path(args.experiment_dir)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    (experiment_dir / "config.json").write_text(
        json.dumps(
            {
                **vars(args),
                "device": str(device),
                "classes": train_dataset.classes,
                "init_mode": init_mode,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    best = -1.0
    stale = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        seen = 0
        for images, targets in train_loader:
            images = images.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = loss_fn(logits, targets)
            loss.backward()
            optimizer.step()
            total_loss += float(loss)
            correct += int((logits.argmax(1) == targets).sum())
            seen += len(targets)

        model.eval()
        y_true: list[int] = []
        y_pred: list[int] = []
        with torch.inference_mode():
            for images, targets in val_loader:
                predictions = model(images.to(device, non_blocking=True)).argmax(1).cpu()
                y_true.extend(targets.tolist())
                y_pred.extend(predictions.tolist())
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "macro_f1": float(f1_score(y_true, y_pred, labels=list(range(827)), average="macro", zero_division=0)),
        }
        row = {
            "epoch": epoch,
            "train_loss": total_loss / len(train_loader),
            "train_accuracy": correct / seen,
            **metrics,
        }
        history.append(row)
        checkpoint = {
            "model": model.state_dict(),
            "classes": train_dataset.classes,
            "architecture": "resnet18",
            "metrics": metrics,
            "epoch": epoch,
            "source_checkpoint": str(args.init),
        }
        torch.save(checkpoint, experiment_dir / "last_model.pt")
        if metrics["macro_f1"] > best:
            best = metrics["macro_f1"]
            stale = 0
            torch.save(checkpoint, experiment_dir / "best_model.pt")
            torch.save(checkpoint, args.out)
        else:
            stale += 1
        (experiment_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(
            f"epoch={epoch} loss={row['train_loss']:.4f} train_acc={row['train_accuracy']:.4f} "
            f"val_acc={metrics['accuracy']:.4f} macro_f1={metrics['macro_f1']:.4f}",
            flush=True,
        )
        scheduler.step()
        if args.patience and stale >= args.patience:
            print(f"early_stopping epoch={epoch} best_macro_f1={best:.4f}", flush=True)
            break

    print(
        json.dumps(
            {
                "best_macro_f1": best,
                "checkpoint": str(Path(args.out).resolve()),
                "init_mode": init_mode,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

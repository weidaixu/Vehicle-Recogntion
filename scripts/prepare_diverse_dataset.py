"""Prepare a 51-class dataset whose unknown class covers every unselected source class."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
from collections import Counter
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def file_hash(path: Path) -> bytes:
    return hashlib.sha256(path.read_bytes()).digest()


def select_per_source_class(
    split_root: Path,
    class_ids: list[str],
    per_class: int,
    seed: int,
    blocked_hashes: set[bytes],
) -> tuple[list[tuple[str, Path]], set[bytes]]:
    """Select a reproducible, duplicate-free quota from every source class."""
    selected: list[tuple[str, Path]] = []
    added: set[bytes] = set()
    for class_id in class_ids:
        files = sorted(
            path
            for path in (split_root / class_id).iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        random.Random(seed + int(class_id)).shuffle(files)
        class_count = 0
        for path in files:
            digest = file_hash(path)
            if digest in blocked_hashes or digest in added:
                continue
            selected.append((class_id, path))
            added.add(digest)
            class_count += 1
            if per_class > 0 and class_count >= per_class:
                break
    return selected, added


def materialize(selected: list[tuple[str, Path]], destination: Path, flatten_unknown: bool) -> None:
    for class_id, source in selected:
        target_dir = destination / ("unknown" if flatten_unknown else class_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = f"{class_id}_{source.name}" if flatten_unknown else source.name
        target = target_dir / name
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="prepared_diverse")
    parser.add_argument("--known-train-per-class", type=int, default=0, help="0 keeps all unique images")
    parser.add_argument("--unknown-train-per-class", type=int, default=12)
    parser.add_argument("--val-per-class", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = (root / args.out).resolve()
    if output == root or root not in output.parents:
        raise ValueError("输出目录必须位于项目目录内部且不能等于项目根目录")
    if output.exists():
        if not args.clean:
            raise FileExistsError(f"输出目录已存在：{output}；如需重建请添加 --clean")
        shutil.rmtree(output)

    known = [line.strip() for line in (root / "classes.txt").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    all_ids = sorted(path.name for path in (root / "train").iterdir() if path.is_dir() and (root / "val" / path.name).is_dir())
    unknown = [class_id for class_id in all_ids if class_id not in set(known)]
    if len(known) != 50 or len(unknown) != 777:
        raise ValueError(f"期望 50 个已知类和 777 个组外类，实际为 {len(known)} 和 {len(unknown)}")

    train_known, train_known_hashes = select_per_source_class(
        root / "train", known, args.known_train_per_class, args.seed, set()
    )
    train_unknown, train_unknown_hashes = select_per_source_class(
        root / "train", unknown, args.unknown_train_per_class, args.seed + 1000, train_known_hashes
    )
    train_hashes = train_known_hashes | train_unknown_hashes
    val_known, val_known_hashes = select_per_source_class(
        root / "val", known, args.val_per_class, args.seed + 2000, train_hashes
    )
    val_unknown, val_unknown_hashes = select_per_source_class(
        root / "val", unknown, args.val_per_class, args.seed + 3000, train_hashes | val_known_hashes
    )

    materialize(train_known, output / "train", flatten_unknown=False)
    materialize(train_unknown, output / "train", flatten_unknown=True)
    materialize(val_known, output / "val", flatten_unknown=False)
    materialize(val_unknown, output / "val", flatten_unknown=True)
    (output / "label_map.json").write_text(json.dumps(known + ["unknown"], indent=2), encoding="utf-8")
    manifest = {
        "known_classes": len(known),
        "unknown_source_classes": len(unknown),
        "train_known": len(train_known),
        "train_unknown": len(train_unknown),
        "val_known": len(val_known),
        "val_unknown": len(val_unknown),
        "train_unknown_source_coverage": len(Counter(class_id for class_id, _ in train_unknown)),
        "val_unknown_source_coverage": len(Counter(class_id for class_id, _ in val_unknown)),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()

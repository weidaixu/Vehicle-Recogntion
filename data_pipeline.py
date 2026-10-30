"""Prepare the 50 selected classes and the unknown class from the teacher dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
from pathlib import Path


def image_files(path: Path):
    return sorted(p for p in path.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"})


def load_info(path: Path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["id"]): row for row in rows}


def choose_classes(train_root: Path, val_root: Path, info: dict, n: int = 50):
    stats = []
    for cid in sorted(info):
        tr = len(image_files(train_root / cid)) if (train_root / cid).exists() else 0
        va = len(image_files(val_root / cid)) if (val_root / cid).exists() else 0
        if tr and va:
            stats.append((min(tr, 2000) + min(va, 1000), cid))
    # Prefer classes with enough images in both splits, then keep ID ordering reproducible.
    return sorted(cid for _, cid in sorted(stats, key=lambda x: (-x[0], x[1]))[:n])


def file_hash(path: Path):
    return hashlib.sha256(path.read_bytes()).digest()


def copy_sample(src: Path, dst: Path, limit: int, seed: int, excluded_hashes=None):
    files = image_files(src)
    random.Random(seed).shuffle(files)
    dst.mkdir(parents=True, exist_ok=True)
    excluded_hashes = set(excluded_hashes or ())
    copied_hashes = set()
    copied = 0
    for p in files:
        digest = file_hash(p)
        if digest in excluded_hashes or digest in copied_hashes:
            continue
        shutil.copy2(p, dst / p.name)
        copied_hashes.add(digest); copied += 1
        if copied >= limit:
            break
    return copied, copied_hashes


def prepare(args):
    root = Path(args.root)
    train_root, val_root = root / "train", root / "val"
    info = load_info(root / "cls_info" / "class_info.json")
    selected = choose_classes(train_root, val_root, info)
    if len(selected) != 50:
        raise RuntimeError(f"Only found {len(selected)} usable classes; expected 50")
    out = root / args.out
    if args.clean and out.exists():
        shutil.rmtree(out)
    (out / "train").mkdir(parents=True, exist_ok=True)
    (out / "val").mkdir(parents=True, exist_ok=True)
    train_hashes, val_hashes = set(), set()
    for cid in selected:
        _, hashes = copy_sample(train_root / cid, out / "train" / cid, args.max_per_class, 10 + int(cid), train_hashes)
        train_hashes.update(hashes)
    for cid in selected:
        _, hashes = copy_sample(val_root / cid, out / "val" / cid, args.max_val_per_class, 20 + int(cid), train_hashes | val_hashes)
        val_hashes.update(hashes)
    unknown = [cid for cid in sorted(info) if cid not in selected]
    for split, src_root, limit in [("train", train_root, args.unknown_train), ("val", val_root, args.unknown_val)]:
        candidates = []
        for cid in unknown:
            files = image_files(src_root / cid) if (src_root / cid).exists() else []
            candidates.extend((cid, p) for p in files)
        rng = random.Random(100 if split == "train" else 200)
        rng.shuffle(candidates)
        dst = out / split / "unknown"
        dst.mkdir(parents=True, exist_ok=True)
        blocked = train_hashes if split == "train" else train_hashes | val_hashes
        added = set(); copied = 0
        for cid, p in candidates:
            digest = file_hash(p)
            if digest in blocked or digest in added:
                continue
            shutil.copy2(p, dst / f"{cid}_{p.name}")
            added.add(digest); copied += 1
            if copied >= limit:
                break
        if split == "train": train_hashes.update(added)
        else: val_hashes.update(added)
    (root / "classes.txt").write_text("\n".join(selected) + "\n", encoding="utf-8")
    (out / "label_map.json").write_text(json.dumps(selected + ["unknown"], ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "selected_classes.json").write_text(json.dumps([{**info[cid], "train_count": len(image_files(train_root/cid)), "val_count": len(image_files(val_root/cid))} for cid in selected], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Selected 50 classes. Prepared data at {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="prepared_final")
    ap.add_argument("--max-per-class", type=int, default=500)
    ap.add_argument("--max-val-per-class", type=int, default=150)
    ap.add_argument("--unknown-train", type=int, default=2500)
    ap.add_argument("--unknown-val", type=int, default=800)
    ap.add_argument("--clean", action="store_true")
    prepare(ap.parse_args())

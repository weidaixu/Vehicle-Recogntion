"""从现有数据、权重和实验记录生成可复验的课程证据，不使用教师测试集。"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
from torch.utils.data import DataLoader
from torchvision.datasets import ImageFolder
from agent_tools import VehicleClassifier
from train import compute_metrics, validate_dataset_contract


def main():
    torch.set_num_threads(4)
    raw = (ROOT / "classes.txt").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "classes.txt 不得带 BOM"
    ids = raw.decode("utf-8").splitlines()
    catalog = {r["id"]: r for r in json.loads((ROOT / "cls_info/class_info.json").read_text(encoding="utf-8"))}
    assert all(cid in catalog for cid in ids)
    contract = validate_dataset_contract(ROOT / "prepared_final", ids)
    classifier = VehicleClassifier(ROOT / "output/model.pt")
    assert classifier.classes == ids + ["unknown"]
    unknown_sources = {}
    counts = {}
    for split in ("train", "val"):
        base = ROOT / "prepared_final" / split
        counts[split] = {cid: len(list((base / cid).glob("*"))) for cid in ids + ["unknown"]}
        sources = Counter(p.name.split("_")[0] for p in (base / "unknown").iterdir() if p.is_file())
        assert all(cid in catalog and cid not in ids for cid in sources)
        # 核实 unknown 文件确实来自对应训练/验证划分的组外车型。
        for path in (base / "unknown").iterdir():
            cid, filename = path.name.split("_", 1)
            origin = ROOT / split / cid / filename
            assert origin.is_file() and hashlib.sha256(origin.read_bytes()).digest() == hashlib.sha256(path.read_bytes()).digest()
        unknown_sources[split] = dict(sorted(sources.items()))
    dataset = ImageFolder(ROOT / "prepared_final/val", transform=classifier.transform)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = classifier.model.to(device)
    ys, ps, errors = [], [], []
    offset = 0
    with torch.inference_mode():
        for images, labels in DataLoader(dataset, batch_size=48, shuffle=False):
            confidence, predictions = model(images.to(device)).softmax(1).max(1)
            predictions[confidence < classifier.threshold] = 50
            for index, (truth, pred, score) in enumerate(zip(labels.tolist(), predictions.cpu().tolist(), confidence.cpu().tolist())):
                ys.append(truth); ps.append(pred)
                if truth != pred:
                    errors.append({"image": str(Path(dataset.samples[offset + index][0]).relative_to(ROOT)), "true": dataset.classes[truth], "predicted": dataset.classes[pred], "confidence": score})
            offset += len(labels)
            print(f"validation {offset}/{len(dataset)}", flush=True)
    metrics = compute_metrics(ys, ps, 51)
    pairs = Counter((e["true"], e["predicted"]) for e in errors)
    experiments = []
    for directory in sorted((ROOT / "output/experiments").iterdir()):
        if not (directory / "metrics.json").exists():
            continue
        metric = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        experiments.append({"name": directory.name, "macro_f1": metric["macro_f1"], "accuracy": metric["accuracy"], "architecture": config.get("architecture"), "lr": config.get("lr"), "pretrained": config.get("pretrained"), "resume": config.get("resume"), "dataset": config.get("dataset")})
    evidence = {"contract": contract, "class_names": {cid: catalog[cid]["name_from_new"] for cid in ids}, "counts": counts, "unknown_sources": unknown_sources, "model_sha256": hashlib.sha256((ROOT / "output/model.pt").read_bytes()).hexdigest(), "threshold": classifier.threshold, "metrics": metrics, "experiments": experiments, "confusions": [{"true": a, "predicted": b, "count": n} for (a, b), n in pairs.most_common(20)], "errors": sorted(errors, key=lambda x: -x["confidence"]), "device": device}
    target = ROOT / "output/course-audit"
    target.mkdir(exist_ok=True)
    (target / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"macro_f1": metrics["macro_f1"], "accuracy": metrics["accuracy"], "errors": len(errors), "contract": contract, "unknown_source_counts": {s: len(v) for s, v in unknown_sources.items()}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

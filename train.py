"""Train, evaluate and batch-predict the 51-class vehicle classifier."""
from __future__ import annotations
import argparse, json, csv, hashlib, random, shutil
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def load_checkpoint(path, map_location="cpu"):
    """Load a checkpoint created locally by this training pipeline."""
    return torch.load(path, map_location=map_location, weights_only=False)


def set_seed(seed: int):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)


def validate_dataset_contract(root, registered_ids):
    root = Path(root)
    expected = list(registered_ids) + ["unknown"]
    if len(registered_ids) != 50 or len(set(registered_ids)) != 50:
        raise ValueError("classes.txt must contain exactly 50 unique IDs")
    if registered_ids != sorted(registered_ids) or any(len(x) != 4 or not x.isdigit() for x in registered_ids):
        raise ValueError("classes.txt IDs must be sorted four-digit values")
    split_files = {}
    counts = {}
    for split in ("train", "val"):
        folders = sorted(p.name for p in (root / split).iterdir() if p.is_dir())
        if folders != expected:
            raise ValueError(f"{split} classes do not match classes.txt + unknown")
        files = [p for cid in expected for p in (root / split / cid).iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]
        if any(not any(p.suffix.lower() in IMAGE_EXTENSIONS for p in (root / split / cid).iterdir()) for cid in expected):
            raise ValueError(f"{split} contains an empty class")
        split_files[split] = files; counts[split] = len(files)
    train_hashes = {hashlib.sha256(p.read_bytes()).digest() for p in split_files["train"]}
    val_hashes = {hashlib.sha256(p.read_bytes()).digest() for p in split_files["val"]}
    if train_hashes & val_hashes:
        raise ValueError("train/val content overlap detected")
    return {"classes": expected, "train_images": counts["train"], "val_images": counts["val"]}


def balanced_class_weights(targets, num_classes):
    counts = torch.bincount(torch.as_tensor(targets), minlength=num_classes).float()
    if torch.any(counts == 0): raise ValueError("all classes must contain training samples")
    return len(targets) / (num_classes * counts)


def compute_metrics(ys, ps, num_classes):
    labels = list(range(num_classes))
    precision, recall, f1, _ = precision_recall_fscore_support(ys, ps, labels=labels, zero_division=0)
    cm = confusion_matrix(ys, ps, labels=labels)
    known = np.asarray(ys) != num_classes - 1
    rejected = np.asarray(ps) == num_classes - 1
    return {
        "accuracy": float(accuracy_score(ys, ps)),
        "macro_precision": float(precision.mean()), "macro_recall": float(recall.mean()), "macro_f1": float(f1.mean()),
        "unknown_recall": float(recall[-1]), "known_rejection_rate": float(rejected[known].mean()) if known.any() else 0.0,
        "per_class_precision": precision.tolist(), "per_class_recall": recall.tolist(), "per_class_f1": f1.tolist(),
        "confusion_matrix": cm.tolist(),
    }


def select_rejection_threshold(ys, probabilities, thresholds):
    probabilities = torch.as_tensor(probabilities)
    confidence, raw_prediction = probabilities.max(dim=1)
    unknown_index = probabilities.shape[1] - 1
    best = None
    for threshold in thresholds:
        prediction = raw_prediction.clone()
        prediction[confidence < float(threshold)] = unknown_index
        metrics = compute_metrics(list(ys), prediction.tolist(), probabilities.shape[1])
        candidate = {"threshold": float(threshold), **metrics}
        if best is None or candidate["macro_f1"] > best["macro_f1"]:
            best = candidate
    return best

def build_model(n, architecture="tinycnn", pretrained=False):
    if architecture == "resnet18":
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        model = models.resnet18(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, n)
        return model
    class TinyCNN(nn.Module):
        def __init__(self, classes):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d(1)
            )
            self.classifier = nn.Linear(128, classes)
        def forward(self, x):
            return self.classifier(self.features(x).flatten(1))
    return TinyCNN(n)

def loaders(root, batch, image_size=96, workers=0):
    tf_train = transforms.Compose([transforms.RandomResizedCrop(image_size, scale=(.72,1.0), ratio=(.8,1.25)), transforms.RandomHorizontalFlip(), transforms.RandomRotation(7), transforms.ColorJitter(.2,.2,.2,.06), transforms.ToTensor(), transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    tf_val = transforms.Compose([transforms.Resize((image_size,image_size)), transforms.ToTensor(), transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    tr = datasets.ImageFolder(Path(root)/"train", transform=tf_train)
    va = datasets.ImageFolder(Path(root)/"val", transform=tf_val)
    if tr.classes != va.classes: raise ValueError(f"train/val class mismatch: {tr.classes} vs {va.classes}")
    common = {"batch_size":batch, "num_workers":workers, "pin_memory":torch.cuda.is_available(), "persistent_workers":workers > 0}
    return tr, va, DataLoader(tr,shuffle=True,**common), DataLoader(va,shuffle=False,**common)

def evaluate(model, loader, device):
    model.eval(); ys=[]; ps=[]
    with torch.no_grad():
        for x,y in loader:
            z=model(x.to(device)).argmax(1).cpu(); ys.extend(y.tolist()); ps.extend(z.tolist())
    return compute_metrics(ys, ps, len(loader.dataset.classes))

def main(a):
    set_seed(a.seed)
    image_size = 224 if a.architecture == "resnet18" else 96
    registered = [x.strip() for x in Path(a.classes).read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    contract = validate_dataset_contract(a.data, registered)
    tr, va, tl, vl = loaders(a.data, a.batch, image_size, a.workers); device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if tr.classes != contract["classes"]: raise ValueError("ImageFolder class indexes do not match the registered label map")
    model=build_model(len(tr.classes), a.architecture, pretrained=a.pretrained).to(device)
    if a.freeze_backbone and a.architecture == "resnet18":
        for p in model.parameters(): p.requires_grad = False
        for p in model.fc.parameters(): p.requires_grad = True
        if a.unfreeze_last:
            for p in model.layer4.parameters(): p.requires_grad = True
    if a.resume:
        previous = load_checkpoint(a.resume, map_location=device)
        model.load_state_dict(previous["model"])
    weights = balanced_class_weights(tr.targets, len(tr.classes)).to(device) if a.balanced_loss else None
    opt=torch.optim.AdamW((p for p in model.parameters() if p.requires_grad),lr=a.lr,weight_decay=a.weight_decay)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=max(1,a.epochs),eta_min=a.lr*.05)
    loss_fn=nn.CrossEntropyLoss(weight=weights,label_smoothing=a.label_smoothing); best=-1; stale=0; history=[]
    out_path=Path(a.out); out_path.parent.mkdir(parents=True,exist_ok=True)
    experiment_dir=Path(a.experiment_dir) if a.experiment_dir else out_path.parent / "experiments" / out_path.stem
    experiment_dir.mkdir(parents=True, exist_ok=True)
    config={k:v for k,v in vars(a).items() if isinstance(v,(str,int,float,bool,type(None)))}
    config.update({"device":str(device),"torch":str(torch.__version__),"cuda":str(torch.version.cuda or "none"),"dataset":contract,"classes":tr.classes})
    (experiment_dir/"config.json").write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding="utf-8")
    if a.eval_only:
        metrics=evaluate(model,vl,device); (experiment_dir/"metrics.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
        print(json.dumps(metrics,ensure_ascii=False)); return
    for epoch in range(1,a.epochs+1):
        model.train(); total=0; correct=0; seen=0
        for x,y in tl:
            x,y=x.to(device,non_blocking=True),y.to(device,non_blocking=True); opt.zero_grad(set_to_none=True)
            logits=model(x); loss=loss_fn(logits,y); loss.backward(); opt.step(); total+=loss.item(); correct+=(logits.argmax(1)==y).sum().item(); seen+=len(y)
        metrics=evaluate(model,vl,device); row={"epoch":epoch,"train_loss":total/len(tl),"train_accuracy":correct/seen,"lr":opt.param_groups[0]["lr"],**metrics}; history.append(row)
        print(f"epoch={epoch} loss={row['train_loss']:.4f} train_acc={row['train_accuracy']:.4f} val_acc={metrics['accuracy']:.4f} macro_f1={metrics['macro_f1']:.4f}",flush=True)
        checkpoint={"model":model.state_dict(),"classes":tr.classes,"metrics":metrics,"architecture":a.architecture,"normalization":{"mean":[.485,.456,.406],"std":[.229,.224,.225]},"training_config":config,"epoch":epoch}
        torch.save(checkpoint,experiment_dir/"last_model.pt")
        if metrics["macro_f1"]>best:
            best=metrics["macro_f1"]; stale=0; torch.save(checkpoint,experiment_dir/"best_model.pt"); torch.save(checkpoint,out_path)
        else: stale+=1
        (experiment_dir/"history.json").write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
        scheduler.step()
        if a.patience and stale >= a.patience:
            print(f"early_stopping epoch={epoch} best_macro_f1={best:.4f}",flush=True); break
    best_checkpoint=load_checkpoint(experiment_dir/"best_model.pt",map_location="cpu"); (experiment_dir/"metrics.json").write_text(json.dumps(best_checkpoint["metrics"],indent=2),encoding="utf-8")
    print(json.dumps({"best_macro_f1":best,"checkpoint":str(out_path),"experiment_dir":str(experiment_dir)},ensure_ascii=False))

def predict(checkpoint, input_dir, output):
    # 与 Web 共用模型、预处理和验证集校准的拒识阈值。
    from agent_tools import VehicleClassifier
    source = Path(input_dir)
    if not source.is_dir():
        raise ValueError("测试图片目录不存在")
    files = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    if not files:
        raise ValueError("测试目录没有支持的图片")
    if len({p.name for p in files}) != len(files):
        raise ValueError("测试目录存在重名图片，无法生成唯一 image_id")
    classifier = VehicleClassifier(checkpoint)
    rows = []
    for path in files:
        result = classifier.classify_car(path)
        rows.append({"image_id": path.name, "predicted_label": result["label"], "confidence": result["confidence"]})
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["image_id","predicted_label","confidence"]); w.writeheader(); w.writerows(rows)
    return rows

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--data",default="prepared_final"); ap.add_argument("--classes",default="classes.txt"); ap.add_argument("--out",default="output/model.pt"); ap.add_argument("--experiment-dir"); ap.add_argument("--epochs",type=int,default=8); ap.add_argument("--batch",type=int,default=32); ap.add_argument("--lr",type=float,default=3e-4); ap.add_argument("--weight-decay",type=float,default=1e-4); ap.add_argument("--label-smoothing",type=float,default=.05); ap.add_argument("--architecture",choices=["tinycnn","resnet18"],default="tinycnn"); ap.add_argument("--pretrained",action="store_true"); ap.add_argument("--freeze-backbone",action="store_true"); ap.add_argument("--unfreeze-last",action="store_true"); ap.add_argument("--balanced-loss",action="store_true"); ap.add_argument("--resume"); ap.add_argument("--eval-only",action="store_true"); ap.add_argument("--patience",type=int,default=0); ap.add_argument("--workers",type=int,default=0); ap.add_argument("--seed",type=int,default=20260909); ap.add_argument("--predict-dir"); ap.add_argument("--predictions",default="predictions.csv"); a=ap.parse_args()
    if a.predict_dir: predict(a.out,a.predict_dir,a.predictions)
    else: main(a)

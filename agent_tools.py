"""DeepSeek agent and real local business tools used by the Web app."""
from __future__ import annotations
import json, os, sqlite3, uuid
from pathlib import Path
import requests
import torch
from PIL import Image
from torchvision import transforms
from train import build_model

class VehicleTools:
    def __init__(self, db="output/vehicle_agent.sqlite"):
        Path(db).parent.mkdir(parents=True,exist_ok=True); self.db=db
        with sqlite3.connect(db) as c: c.execute("create table if not exists favorites(id text primary key, label text, title text, created_at text default current_timestamp)")
    def query_car_info(self, label):
        info=json.loads(Path("cls_info/class_info.json").read_text(encoding="utf-8")); row=next((r for r in info if r["id"]==label),None)
        return {"ok":bool(row),"data":row or {"id":label,"name_from_new":"unknown"}}
    def add_car_favorite(self, label, title="我的车型收藏"):
        if label=="unknown": return {"ok":False,"error":"unknown 不能作为确定车型收藏"}
        with sqlite3.connect(self.db) as c: c.execute("insert or replace into favorites(id,label,title) values(?,?,?)",(str(uuid.uuid4()),label,title))
        return {"ok":True,"label":label,"title":title}
    def list_favorites(self):
        with sqlite3.connect(self.db) as c: rows=[dict(zip(["id","label","title","created_at"],r)) for r in c.execute("select id,label,title,created_at from favorites order by created_at desc")]
        return {"ok":True,"items":rows}
    def delete_favorite(self, favorite_id):
        with sqlite3.connect(self.db) as c:
            changed = c.execute("delete from favorites where id=?", (favorite_id,)).rowcount
        return {"ok": bool(changed), "deleted_id": favorite_id}

class VehicleClassifier:
    def __init__(self, checkpoint="output/model.pt"):
        path = Path(checkpoint)
        if not path.exists():
            raise FileNotFoundError(f"模型不存在：{path}")
        ck = torch.load(path, map_location="cpu", weights_only=False)
        self.classes = ck["classes"]
        self.metrics = ck.get("metrics", {})
        self.threshold = float(ck.get("rejection_threshold", 0.18))
        self.model = build_model(len(self.classes), ck.get("architecture", "tinycnn"))
        self.model.load_state_dict(ck["model"])
        self.model.eval()
        image_size = 224 if ck.get("architecture", "tinycnn") == "resnet18" else 96
        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)), transforms.ToTensor(),
            transforms.Normalize([.485,.456,.406], [.229,.224,.225]),
        ])

    def classify_car(self, image, threshold=None, top_k=3):
        threshold = self.threshold if threshold is None else float(threshold)
        if not isinstance(image, Image.Image):
            if hasattr(image, "seek"):
                image.seek(0)
            image = Image.open(image)
        with torch.no_grad():
            probabilities = self.model(self.transform(image.convert("RGB")).unsqueeze(0)).softmax(1)[0]
        values, indices = probabilities.topk(min(top_k, len(self.classes)))
        top = [{"label": self.classes[int(i)], "confidence": float(v)} for v, i in zip(values, indices)]
        predicted = top[0]["label"]
        rejected = predicted == "unknown" or top[0]["confidence"] < threshold
        return {"ok": True, "label": "unknown" if rejected else predicted,
                "raw_label": predicted, "confidence": top[0]["confidence"],
                "top_k": top, "rejected": rejected, "threshold": threshold}

def call_deepseek(messages, tools):
    key=os.getenv("DEEPSEEK_API_KEY","").strip()
    if not key: raise RuntimeError("请设置 DEEPSEEK_API_KEY 环境变量")
    r=requests.post("https://api.deepseek.com/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json={"model":"deepseek-v4-flash","messages":messages,"tools":tools,"tool_choice":"auto","temperature":.2},timeout=(10,90)); r.raise_for_status(); return r.json()

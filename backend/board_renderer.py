from __future__ import annotations
import json, textwrap, uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

BG="#141713"; CARD="#24231f"; INK="#F3EEDD"; MUTED="#9C9A90"; RED="#D92D32"
def font(size,bold=False):
    choices=[Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),Path("C:/Windows/Fonts/arial.ttf")]
    return ImageFont.truetype(str(next(p for p in choices if p.exists())),size)
def resolve_local(url):
    parts=url.split("/api/local-image/")
    return Path(parts[1]) if len(parts)==2 else None
def render_board(class_id,name,design,views,out_dir="output/boards"):
    canvas=Image.new("RGB",(1800,1200),BG); d=ImageDraw.Draw(canvas); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    d.text((80,64),"DRIVESCOPE / DESIGN ARCHIVE",font=font(26,True),fill=RED)
    d.text((80,112),name,font=font(64,True),fill=INK); d.text((82,192),f"CLASS {class_id}",font=font(22),fill=MUTED)
    for i,item in enumerate(views[:6]):
        p=resolve_local(item.get("url","")); x=80+(i%3)*555; y=250+(i//3)*350
        if p and p.exists():
            im=Image.open(p).convert("RGB"); im=ImageOps.fit(im,(515,270)); canvas.paste(im,(x,y))
        d.text((x,y+282),f"{i+1:02d}  {item.get('view_hint','未标注视角')}",font=font(19),fill=MUTED)
    tx,ty=80,980
    summary=design.get("summary","")
    for line in textwrap.wrap(summary,width=58)[:4]: d.text((tx,ty),line,font=font(23),fill=INK); ty+=34
    board_id=str(uuid.uuid4()); image_path=out/f"{board_id}.jpg"; canvas.save(image_path,quality=92)
    manifest={"board_id":board_id,"class_id":class_id,"name":name,"sources":views}
    (out/f"{board_id}.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return board_id,image_path

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..services import services
from ..wikimedia import search_commons

router=APIRouter(prefix="/api")
EXT={".jpg",".jpeg",".png",".bmp"}
def local_views(class_id,limit=8):
    rows=[]
    for split in ("val","train"):
        root=Path(split)/class_id
        if not root.exists(): continue
        for p in sorted(root.iterdir()):
            if p.suffix.lower() in EXT:
                rows.append({"url":f"/api/local-image/{split}/{class_id}/{p.name}","thumbnail_url":f"/api/local-image/{split}/{class_id}/{p.name}","source_kind":"local_dataset","view_hint":"未标注视角","author":"课程数据集","license_name":"仅用于课程实训","license_url":"","source_page":"","modified":False})
                if len(rows)>=limit:return rows
    return rows

@router.get("/vehicle-views/{class_id}")
def vehicle_views(class_id:str,network:bool=True,limit:int=12):
    car=services.catalog.get(class_id)
    if not car: raise HTTPException(404,"class not found")
    rows=local_views(class_id,min(limit,8))
    if network and len(rows)<limit:
        try: rows.extend(search_commons(car["name_from_new"].replace("_"," "),limit-len(rows)))
        except Exception: pass
    tid=services.add_trace("search_vehicle_views","success",{"class_id":class_id,"count":len(rows)})
    return {"items":rows[:limit],"trace_id":tid,"offline_fallback":not any(x["source_kind"]=="wikimedia" for x in rows)}

@router.get("/local-image/{split}/{class_id}/{filename}")
def local_image(split:str,class_id:str,filename:str):
    if split not in {"train","val"} or class_id not in services.catalog: raise HTTPException(404,"image not found")
    root=(Path(split)/class_id).resolve(); path=(root/Path(filename).name).resolve()
    if path.parent!=root or not path.exists(): raise HTTPException(404,"image not found")
    return FileResponse(path)

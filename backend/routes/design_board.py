from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from ..schemas import BoardRequest
from ..services import services
from ..board_renderer import render_board

router=APIRouter(prefix="/api")
@router.post("/design-board")
def create_board(req:BoardRequest):
    car=services.catalog.get(req.class_id)
    if not car: raise HTTPException(404,"class not found")
    views=[{"url":x,"view_hint":"未标注视角","source_kind":"local_dataset","author":"课程数据集","license_name":"仅用于课程实训","source_page":"","modified":False} for x in req.image_paths]
    board_id,_=render_board(req.class_id,car["name_from_new"],req.design_language.model_dump(),views)
    tid=services.add_trace("build_design_board","success",{"class_id":req.class_id,"board_id":board_id})
    return {"board_id":board_id,"board_url":f"/api/design-board/{board_id}.jpg","manifest_url":f"/api/design-board/{board_id}.json","trace_id":tid}
@router.get("/design-board/{filename}")
def board_file(filename:str):
    path=(Path("output/boards")/Path(filename).name)
    if not path.exists(): raise HTTPException(404,"board not found")
    return FileResponse(path)

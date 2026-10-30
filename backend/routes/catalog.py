from fastapi import APIRouter, HTTPException, Query
from ..services import services

router=APIRouter(prefix="/api")

@router.get("/cars")
def search_cars(q:str="",limit:int=Query(20,ge=1,le=100)):
    query=q.casefold().strip(); rows=[]
    for cid,row in sorted(services.catalog.items()):
        if not query or query in cid.casefold() or query in row["name_from_new"].casefold(): rows.append(row)
    return rows[:limit]

@router.get("/cars/{class_id}")
def car_detail(class_id:str):
    if class_id not in services.catalog: raise HTTPException(404,"class not found")
    result=services.catalog[class_id]
    services.add_trace("query_car_info","success",{"class_id":class_id})
    return result

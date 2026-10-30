from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from ..services import services

router=APIRouter(prefix="/api")

@router.post("/classify")
async def classify(image:UploadFile=File(...),threshold:float|None=Form(None)):
    if threshold is not None and not .05 <= threshold <= .80: raise HTTPException(422,"threshold must be between 0.05 and 0.80")
    raw=await image.read()
    if len(raw)>15*1024*1024: raise HTTPException(413,"image exceeds 15 MB")
    try: pil=Image.open(BytesIO(raw)); pil.verify(); pil=Image.open(BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError,OSError): raise HTTPException(415,"invalid image")
    if not services.classifier: raise HTTPException(503,"model unavailable")
    result=services.classifier.classify_car(pil,threshold=threshold)
    for item in result["top_k"]: item["name"]=services.catalog.get(item["label"],{}).get("name_from_new","unknown")
    result["name"]=services.catalog.get(result["label"],{}).get("name_from_new","unknown")
    result["trace_id"]=services.add_trace("classify_car","success",{"filename":image.filename,"label":result["label"],"confidence":result["confidence"]})
    return result

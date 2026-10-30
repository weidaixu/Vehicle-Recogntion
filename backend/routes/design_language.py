import uuid
from fastapi import APIRouter, HTTPException
from ..schemas import DesignLanguageRequest, DesignLanguageResponse
from ..services import services
from ..deepseek_client import generate_design_language

router=APIRouter(prefix="/api")
@router.post("/design-language",response_model=DesignLanguageResponse)
def design_language(req:DesignLanguageRequest):
    car=services.catalog.get(req.class_id)
    if not car: raise HTTPException(404,"class not found")
    try: result=generate_design_language(car,req.user_focus)
    except RuntimeError as exc: raise HTTPException(503,str(exc))
    except Exception: raise HTTPException(502,"design-language generation failed")
    trace_id=services.add_trace("generate_design_language","success",{"class_id":req.class_id})
    return DesignLanguageResponse(**result,trace_id=trace_id)

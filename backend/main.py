from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import load_project_env

load_project_env()

from .schemas import StatusResponse
from .services import services
from .routes.classification import router as classification_router
from .routes.catalog import router as catalog_router
from .routes.design_language import router as design_language_router
from .routes.vehicle_views import router as vehicle_views_router
from .routes.design_board import router as design_board_router
from .routes.agent import router as agent_router
from .routes.archives import router as archives_router

app=FastAPI(title="DriveScope API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(classification_router)
app.include_router(catalog_router)
app.include_router(design_language_router)
app.include_router(vehicle_views_router)
app.include_router(design_board_router)
app.include_router(agent_router)
app.include_router(archives_router)

@app.get("/api/health")
def health(): return {"ok":True}

@app.get("/api/status",response_model=StatusResponse)
def status():
    metrics=services.classifier.metrics if services.classifier else {}
    return StatusResponse(model_ready=services.classifier is not None,class_count=len(services.classifier.classes) if services.classifier else 0,macro_f1=float(metrics.get("macro_f1",0)),deepseek_configured=bool(os.getenv("DEEPSEEK_API_KEY")),webgl_assets_ready=Path("frontend/public/assets/showroom-original.jpg").exists())

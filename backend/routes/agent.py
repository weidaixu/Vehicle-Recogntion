from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from ..agent_runtime import AgentProtocolError, AgentRuntime
from ..services import services

router = APIRouter(prefix="/api")
IMAGE_ROOT = Path("output/session-images")


class AgentRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=12000)


def runtime() -> AgentRuntime:
    return AgentRuntime(store=services.store, classifier=services.classifier, catalog=services.catalog)


def _run_or_http(**kwargs):
    if not services.classifier:
        raise HTTPException(503, "本地视觉模型不可用")
    try:
        return runtime().run(**kwargs)
    except AgentProtocolError as exc:
        message = str(exc)
        if "DEEPSEEK_API_KEY" in message or "DeepSeek" in message:
            raise HTTPException(503, message)
        raise HTTPException(422, message)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@router.post("/agent")
def run_agent(req: AgentRequest):
    return _run_or_http(session_id=req.session_id, user_message=req.message)


@router.post("/agent/upload")
async def run_agent_upload(
    image: UploadFile = File(...),
    session_id: str = Form(..., min_length=1, max_length=120),
    message: str = Form(..., min_length=1, max_length=12000),
):
    raw = await image.read(15 * 1024 * 1024 + 1)
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(413, "图片不能超过 15 MB")
    try:
        pil = Image.open(BytesIO(raw))
        pil.verify()
        Image.open(BytesIO(raw)).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(415, "图片无法解码，请上传 JPG、PNG 等有效图片")
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    image_ref = f"img_{uuid.uuid4().hex}.jpg"
    image_path = IMAGE_ROOT / image_ref
    image_path.write_bytes(raw)
    return _run_or_http(session_id=session_id, user_message=message, image_ref=image_ref, image_path=image_path, image_filename=image.filename or image_ref)


@router.get("/session/{session_id}")
def get_session(session_id: str):
    return services.store.get_session(session_id)

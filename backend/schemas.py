from __future__ import annotations
from pydantic import BaseModel, Field

class StatusResponse(BaseModel):
    model_ready: bool
    class_count: int
    macro_f1: float
    deepseek_configured: bool
    webgl_assets_ready: bool

class ToolTrace(BaseModel):
    tool: str
    status: str
    arguments: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    duration_ms: int = 0
    call_id: str | None = None
    summary: dict = Field(default_factory=dict)

class DesignLanguageRequest(BaseModel):
    session_id: str
    class_id: str
    user_focus: str = ""

class DesignLanguageResponse(BaseModel):
    summary: str
    proportions: str
    lighting_signature: str
    surface_language: str
    aerodynamics: str
    brand_cues: str
    limitations: str
    trace_id: str

class BoardRequest(BaseModel):
    class_id: str
    design_language: DesignLanguageResponse
    image_paths: list[str]

class AgentResponse(BaseModel):
    session_id: str
    answer: str
    classification: dict | None = None
    design_language: dict | None = None
    views: list[dict] = Field(default_factory=list)
    board_url: str | None = None
    trace: list[ToolTrace] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)

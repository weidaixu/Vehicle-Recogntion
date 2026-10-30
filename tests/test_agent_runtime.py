from __future__ import annotations

import json
from pathlib import Path

from backend.agent_runtime import AgentRuntime
from backend.session_store import SessionStore


CAR = {"id": "0000", "name_from_new": "江铃_凯运", "type_info": "轻型卡车"}
DESIGN = {
    "summary": "低重心与紧致曲面形成清晰的功能表达。",
    "proportions": "前后比例紧凑",
    "lighting_signature": "横向灯组",
    "surface_language": "收紧的折面",
    "aerodynamics": "仅根据图像观察",
    "brand_cues": "品牌信息不足",
    "limitations": "未推断尺寸和动力参数",
}


class ScriptedModel:
    def __init__(self, calls: list[dict]):
        self.calls = calls
        self.requests: list[dict] = []

    def __call__(self, messages, tools, tool_choice=None):
        self.requests.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        return self.calls[len(self.requests) - 1]


def tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
                }],
            }
        }]
    }


def final_answer(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def make_runtime(tmp_path: Path, model: ScriptedModel, classifier=None) -> AgentRuntime:
    class KnownClassifier:
        def classify_car(self, image, threshold=0.26):
            return {
                "ok": True,
                "label": "0000",
                "raw_label": "0000",
                "confidence": 0.93,
                "rejected": False,
                "threshold": threshold,
                "top_k": [{"label": "0000", "confidence": 0.93}],
            }

    return AgentRuntime(
        store=SessionStore(tmp_path / "agent.sqlite"),
        classifier=classifier or KnownClassifier(),
        catalog={"0000": CAR},
        model_call=model,
        design_generator=lambda car, focus="": DESIGN,
        view_search=lambda class_id, limit=8: [{
            "url": f"/api/local-image/val/{class_id}/car.jpg",
            "thumbnail_url": f"/api/local-image/val/{class_id}/car.jpg",
            "source_kind": "local_dataset",
            "view_hint": "未标注视角",
            "author": "课程数据集",
            "license_name": "仅用于课程实训",
            "license_url": "",
            "source_page": "",
            "modified": False,
        }],
        board_builder=lambda *args, **kwargs: ("board-1", "output/boards/board-1.jpg"),
    )


def test_first_model_turn_requests_classification_with_controlled_image_ref(tmp_path):
    model = ScriptedModel([
        tool_call("c1", "classify_car", {"image_ref": "img-123.jpg", "threshold": 0.26}),
        final_answer("已完成识别。"),
    ])
    runtime = make_runtime(tmp_path, model)
    (tmp_path / "img-123.jpg").write_bytes(b"fake-bytes")

    result = runtime.run("session-1", "这是什么车？", image_ref="img-123.jpg", image_path=tmp_path / "img-123.jpg")

    assert result["classification"]["label"] == "0000"
    assert result["trace"][0]["tool"] == "classify_car"
    assert result["trace"][0]["arguments"] == {"image_ref": "img-123.jpg", "threshold": 0.26}
    assert isinstance(result["trace"][0]["duration_ms"], int)
    first = model.requests[0]
    assert first["tool_choice"] == {"type": "function", "function": {"name": "classify_car"}}
    assert any("img-123.jpg" in str(message) for message in first["messages"])
    assert "data:image" not in json.dumps(first["messages"])
    assert "fake-bytes" not in json.dumps(first["messages"])


def test_model_drives_tool_order_and_session_context_is_reused(tmp_path):
    model = ScriptedModel([
        tool_call("c1", "classify_car", {"image_ref": "img-123.jpg", "threshold": 0.26}),
        tool_call("c2", "query_car_info", {"class_id": "0000"}),
        tool_call("c3", "search_vehicle_views", {"class_id": "0000", "limit": 1}),
        tool_call("c4", "generate_design_language", {"class_id": "0000", "focus": "比例"}),
        tool_call("c5", "build_design_board", {"class_id": "0000"}),
        tool_call("c6", "save_vehicle_archive", {"class_id": "0000", "title": "车展观察"}),
        final_answer("已建立可检索的车型档案。"),
        final_answer("车展观察。"),
    ])
    runtime = make_runtime(tmp_path, model)
    (tmp_path / "img-123.jpg").write_bytes(b"fake-bytes")

    first = runtime.run("session-1", "识别并建立档案", image_ref="img-123.jpg", image_path=tmp_path / "img-123.jpg")
    second = runtime.run("session-1", "刚才那辆车的档案叫什么？")

    assert [item["tool"] for item in first["trace"]] == [
        "classify_car", "query_car_info", "search_vehicle_views",
        "generate_design_language", "build_design_board", "save_vehicle_archive",
    ]
    assert first["trace"][3]["status"] == "success"
    assert first["trace"][4]["result"]["board_id"] == "board-1"
    assert second["session_id"] == "session-1"
    state = runtime.store.get_session("session-1")
    assert state["image_ref"] == "img-123.jpg"
    assert state["classification"]["label"] == "0000"
    assert len(state["messages"]) >= 2
    assert runtime.store.search_archives("车展观察")[0]["title"] == "车展观察"


def test_reasoning_content_is_replayed_for_follow_up_model_turn(tmp_path):
    first_response = tool_call("c1", "classify_car", {"image_ref": "img-123.jpg", "threshold": 0.26})
    first_response["choices"][0]["message"]["reasoning_content"] = "先完成图片分类。"
    model = ScriptedModel([first_response, final_answer("已完成识别。")])
    runtime = make_runtime(tmp_path, model)
    (tmp_path / "img-123.jpg").write_bytes(b"fake-bytes")

    runtime.run("session-reasoning", "这是什么车？", image_ref="img-123.jpg", image_path=tmp_path / "img-123.jpg")

    assistant_message = next(
        message for message in model.requests[1]["messages"]
        if message["role"] == "assistant"
    )
    assert assistant_message["reasoning_content"] == "先完成图片分类。"


def test_unknown_forces_programmatic_stop_after_classify(tmp_path):
    class UnknownClassifier:
        def classify_car(self, image, threshold=0.26):
            return {"ok": True, "label": "unknown", "raw_label": "unknown", "confidence": 0.08,
                    "rejected": True, "threshold": threshold, "top_k": [{"label": "unknown", "confidence": 0.08}]}

    model = ScriptedModel([tool_call("c1", "classify_car", {"image_ref": "img-unknown.jpg", "threshold": 0.26})])
    runtime = make_runtime(tmp_path, model, classifier=UnknownClassifier())
    (tmp_path / "img-unknown.jpg").write_bytes(b"fake-bytes")

    result = runtime.run("session-unknown", "继续分析", image_ref="img-unknown.jpg", image_path=tmp_path / "img-unknown.jpg")

    assert len(model.requests) == 1
    assert [item["tool"] for item in result["trace"]] == ["classify_car"]
    assert result["classification"]["label"] == "unknown"
    assert "未识别为本组支持的车型" in result["answer"]


def test_new_image_clears_previous_vehicle_context(tmp_path):
    store = SessionStore(tmp_path / "context.sqlite")
    store.update_context("s", classification={"label": "0000"}, design_language=DESIGN,
                         views=[{"url": "old.jpg"}], board_url="old-board.jpg")
    store.register_image("s", "new.jpg", tmp_path / "new.jpg")
    state = store.get_session("s")
    assert state["classification"] is None
    assert state["design_language"] is None
    assert state["views"] == []
    assert state["board_url"] is None


def test_unknown_batch_is_fully_resolved_before_followup(tmp_path):
    class UnknownClassifier:
        threshold = 0.26

        def classify_car(self, *args, **kwargs):
            return {"label": "unknown", "confidence": 0.9, "rejected": True, "top_k": []}

    batch = tool_call("c1", "classify_car", {"image_ref": "new.jpg"})
    batch["choices"][0]["message"]["tool_calls"] += tool_call(
        "c2", "query_car_info", {"class_id": "0000"})["choices"][0]["message"]["tool_calls"]
    model = ScriptedModel([batch, final_answer("请重新拍摄。")])
    runtime = make_runtime(tmp_path, model, UnknownClassifier())
    (tmp_path / "new.jpg").write_bytes(b"test")
    result = runtime.run("s", "识别并查询", "new.jpg", tmp_path / "new.jpg")
    assert [t["status"] for t in result["trace"]] == ["success", "failed"]
    runtime.run("s", "怎么办？")
    replies = [m["tool_call_id"] for m in model.requests[-1]["messages"] if m["role"] == "tool"]
    assert replies == ["c1", "c2"]


def test_agent_cannot_lower_calibrated_threshold(tmp_path):
    runtime = make_runtime(tmp_path, ScriptedModel([]))
    runtime.classifier.threshold = 0.26
    args = runtime._validate_args("classify_car", {"image_ref": "x.jpg", "threshold": 0.05}, {"image_ref": "x.jpg"})
    assert args["threshold"] == 0.26

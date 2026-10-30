"""DeepSeek function-calling runtime and validated local tool dispatch."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from .deepseek_client import call_deepseek
from .session_store import SessionStore


TOOLS = [
    {"type": "function", "function": {"name": "classify_car", "description": "使用本组训练的51类视觉模型识别受控图片引用。", "parameters": {"type": "object", "properties": {"image_ref": {"type": "string"}, "threshold": {"type": "number", "minimum": 0.05, "maximum": 0.8}}, "required": ["image_ref"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "query_car_info", "description": "读取已识别车型的课程资料。", "parameters": {"type": "object", "properties": {"class_id": {"type": "string", "pattern": "^[0-9]{4}$"}}, "required": ["class_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "search_vehicle_views", "description": "检索本地或带授权信息的车型多视角资料。", "parameters": {"type": "object", "properties": {"class_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 12}}, "required": ["class_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "generate_design_language", "description": "根据车型资料生成结构化、带局限说明的设计语言分析。", "parameters": {"type": "object", "properties": {"class_id": {"type": "string"}, "focus": {"type": "string", "maxLength": 160}}, "required": ["class_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "build_design_board", "description": "把当前车型、设计分析和视觉档案生成可下载图板。", "parameters": {"type": "object", "properties": {"class_id": {"type": "string"}}, "required": ["class_id"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "save_vehicle_archive", "description": "将当前车型研究结果保存到可检索档案。", "parameters": {"type": "object", "properties": {"class_id": {"type": "string"}, "title": {"type": "string", "maxLength": 120}}, "required": ["class_id", "title"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "search_archive_history", "description": "检索本地已保存的车型档案。", "parameters": {"type": "object", "properties": {"query": {"type": "string", "maxLength": 100}, "limit": {"type": "integer", "minimum": 1, "maximum": 30}}, "required": [], "additionalProperties": False}}},
]


class AgentProtocolError(RuntimeError):
    pass


def _default_views(class_id: str, limit: int = 8) -> list[dict]:
    from .routes.vehicle_views import local_views
    from .wikimedia import search_commons

    rows = local_views(class_id, min(limit, 8))
    if len(rows) < limit:
        try:
            rows.extend(search_commons(class_id, limit - len(rows)))
        except Exception:
            pass
    return rows[:limit]


def _default_board(*args, **kwargs):
    from .board_renderer import render_board
    return render_board(*args, **kwargs)


class AgentRuntime:
    def __init__(self, *, store: SessionStore, classifier, catalog: dict, model_call: Callable | None = None, design_generator: Callable | None = None, view_search: Callable | None = None, board_builder: Callable | None = None, max_rounds: int = 12):
        self.store = store
        self.classifier = classifier
        self.catalog = catalog
        self.model_call = model_call or call_deepseek
        self.design_generator = design_generator
        self.view_search = view_search or _default_views
        self.board_builder = board_builder or _default_board
        self.max_rounds = max_rounds

    def _model_messages(self, session_id: str) -> list[dict]:
        system = {"role": "system", "content": "你是 DriveScope 车展车型视觉研究智能体。新图片任务的第一步必须调用 classify_car；图片不会发送给你，只能把受控 image_ref 原样传给工具。必须根据工具结果决定下一步，不能编造分类、资料、图片或保存状态。识别为 unknown 或低置信度后立即停止后续车型工具，明确告诉用户未识别为本组支持的车型。对于建立研究档案的请求，按需调用 query_car_info、generate_design_language、search_vehicle_views、build_design_board、save_vehicle_archive；工具顺序由你根据上下文决定。最终用中文简洁总结真实完成和失败的部分。"}
        messages = [system]
        for item in self.store.get_messages(session_id):
            message = {"role": item["role"], "content": item["content"]}
            metadata = item.get("metadata") or {}
            if item["role"] == "assistant" and metadata.get("tool_calls"):
                message["tool_calls"] = metadata["tool_calls"]
            if item["role"] == "assistant" and isinstance(metadata.get("reasoning_content"), str):
                message["reasoning_content"] = metadata["reasoning_content"]
            if item["role"] == "tool":
                if metadata.get("tool_call_id"):
                    message["tool_call_id"] = metadata["tool_call_id"]
                if metadata.get("name"):
                    message["name"] = metadata["name"]
            messages.append(message)
        return messages

    def _validate_args(self, name: str, args: dict, session: dict) -> dict:
        if not isinstance(args, dict):
            raise AgentProtocolError(f"工具 {name} 参数必须是 JSON 对象")
        allowed = {item["function"]["name"]: set(item["function"]["parameters"]["properties"]) for item in TOOLS}[name]
        if set(args) - allowed:
            raise AgentProtocolError(f"工具 {name} 包含未允许的参数")
        if name == "classify_car":
            ref = args.get("image_ref")
            if not isinstance(ref, str) or ref != session.get("image_ref"):
                raise AgentProtocolError("classify_car 只能使用当前会话的受控 image_ref")
            threshold = getattr(self.classifier, "threshold", 0.26)
            if not isinstance(threshold, (int, float)) or not 0.05 <= float(threshold) <= 0.8:
                raise AgentProtocolError("threshold 必须在 0.05 到 0.80 之间")
            return {"image_ref": ref, "threshold": float(threshold)}
        if name in {"query_car_info", "search_vehicle_views", "generate_design_language", "build_design_board", "save_vehicle_archive"}:
            class_id = args.get("class_id")
            classification = session.get("classification") or {}
            if classification.get("rejected"):
                raise AgentProtocolError("低置信度结果不能继续执行确定车型业务")
            if class_id != classification.get("label"):
                raise AgentProtocolError("工具使用的 class_id 与当前识别结果不一致")
            if class_id not in self.catalog or class_id == "unknown":
                raise AgentProtocolError("当前没有可供车型业务使用的确定 class_id")
        if name == "search_vehicle_views":
            limit = args.get("limit", 8)
            if not isinstance(limit, int) or not 1 <= limit <= 12:
                raise AgentProtocolError("limit 必须是 1 到 12 的整数")
            return {"class_id": args["class_id"], "limit": limit}
        if name == "generate_design_language":
            focus = args.get("focus", "")
            if not isinstance(focus, str) or len(focus) > 160:
                raise AgentProtocolError("focus 参数过长")
            return {"class_id": args["class_id"], "focus": focus}
        if name == "save_vehicle_archive":
            title = args.get("title", "车型视觉研究")
            if not isinstance(title, str) or not title.strip() or len(title) > 120:
                raise AgentProtocolError("档案标题不能为空且不能超过120字")
            return {"class_id": args["class_id"], "title": title.strip()}
        if name == "search_archive_history":
            query = args.get("query", "")
            limit = args.get("limit", 20)
            if not isinstance(query, str) or len(query) > 100 or not isinstance(limit, int) or not 1 <= limit <= 30:
                raise AgentProtocolError("历史检索参数无效")
            return {"query": query, "limit": limit}
        return {"class_id": args["class_id"]} if name != "classify_car" else args

    def _execute(self, name: str, args: dict, session_id: str) -> dict:
        session = self.store.get_session(session_id)
        if name == "classify_car":
            path = self.store.get_image_path(session_id, args["image_ref"])
            if not path or not path.exists():
                raise AgentProtocolError("当前会话的图片引用不存在")
            result = self.classifier.classify_car(path, threshold=args["threshold"])
            for item in result.get("top_k", []):
                item["name"] = self.catalog.get(item["label"], {}).get("name_from_new", "unknown")
            result["name"] = self.catalog.get(result["label"], {}).get("name_from_new", "unknown")
            self.store.update_context(session_id, classification=result)
            return result
        if name == "query_car_info":
            return self.catalog[args["class_id"]]
        if name == "search_vehicle_views":
            views = self.view_search(args["class_id"], args["limit"])
            self.store.update_context(session_id, views=views)
            return {"items": views, "count": len(views), "offline_fallback": not any(v.get("source_kind") == "wikimedia" for v in views)}
        if name == "generate_design_language":
            if not self.design_generator:
                from .deepseek_client import generate_design_language
                result = generate_design_language(self.catalog[args["class_id"]], args["focus"])
            else:
                result = self.design_generator(self.catalog[args["class_id"]], args["focus"])
            self.store.update_context(session_id, design_language=result)
            return result
        if name == "build_design_board":
            car = self.catalog[args["class_id"]]
            if not session.get("design_language"):
                raise AgentProtocolError("请先生成设计语言，再建立设计板")
            board_id, _ = self.board_builder(args["class_id"], car["name_from_new"], session["design_language"], session.get("views", []))
            board_url = f"/api/design-board/{board_id}.jpg"
            self.store.update_context(session_id, board_url=board_url)
            return {"board_id": board_id, "board_url": board_url, "manifest_url": f"/api/design-board/{board_id}.json"}
        if name == "save_vehicle_archive":
            if not session.get("classification") or not session.get("design_language"):
                raise AgentProtocolError("档案需要先完成识别和设计语言分析")
            record = self.store.save_archive(session_id, args["class_id"], args["title"], session.get("image_ref"), session["design_language"], session.get("views", []), session.get("board_url"))
            return {"archive_id": record["archive_id"], "title": record["title"], "class_id": record["class_id"]}
        if name == "search_archive_history":
            items = self.store.search_archives(args["query"], args["limit"])
            return {"items": items, "count": len(items)}
        raise AgentProtocolError(f"未知工具：{name}")

    @staticmethod
    def _trace_result(name: str, result: dict) -> dict:
        if name == "search_vehicle_views":
            return {"count": result.get("count", 0), "offline_fallback": result.get("offline_fallback", True)}
        if name == "search_archive_history":
            return {"count": result.get("count", 0), "titles": [x.get("title") for x in result.get("items", [])[:5]]}
        if name == "generate_design_language":
            return {"summary": result.get("summary", ""), "fields": [key for key in result if key != "limitations"]}
        if name == "classify_car":
            return {key: result.get(key) for key in ("label", "raw_label", "confidence", "rejected")}
        return {key: result.get(key) for key in ("id", "name_from_new", "type_info", "board_id", "board_url", "archive_id", "title") if key in result}

    def run(self, session_id: str, user_message: str, image_ref: str | None = None, image_path: str | Path | None = None, image_filename: str = "") -> dict:
        self.store.ensure_session(session_id)
        if image_ref:
            if not image_path:
                raise AgentProtocolError("新图片必须同时提供本地路径")
            self.store.register_image(session_id, image_ref, image_path, image_filename)
        session = self.store.get_session(session_id)
        if not user_message.strip():
            raise AgentProtocolError("请输入自然语言任务")
        prompt = user_message.strip()
        if image_ref:
            prompt += f"\n受控 image_ref：{image_ref}"
        self.store.append_message(session_id, "user", prompt, image_ref=image_ref)
        force_classify = bool(image_ref)
        trace: list[dict] = []
        for round_index in range(self.max_rounds):
            choice = {"type": "function", "function": {"name": "classify_car"}} if force_classify else "auto"
            response = self.model_call(self._model_messages(session_id), TOOLS, tool_choice=choice)
            try:
                message = response["choices"][0]["message"]
                if not isinstance(message, dict):
                    raise TypeError("message must be an object")
            except (KeyError, IndexError, TypeError) as exc:
                raise AgentProtocolError("DeepSeek 返回了无法解析的消息") from exc
            tool_calls = message.get("tool_calls") or []
            if not isinstance(tool_calls, list) or any(
                not isinstance(call, dict) or not isinstance(call.get("id"), str)
                or not call["id"] or not isinstance(call.get("function"), dict)
                or not isinstance(call["function"].get("name"), str)
                or not isinstance(call["function"].get("arguments", "{}"), str)
                for call in tool_calls
            ) or len({call["id"] for call in tool_calls}) != len(tool_calls):
                raise AgentProtocolError("DeepSeek 返回了无效的工具调用结构")
            if force_classify and tool_calls and tool_calls[0]["function"]["name"] != "classify_car":
                raise AgentProtocolError("图片任务的第一条工具调用必须是 classify_car")
            assistant_metadata = {"tool_calls": tool_calls} if tool_calls else {}
            reasoning_content = message.get("reasoning_content")
            if isinstance(reasoning_content, str):
                assistant_metadata["reasoning_content"] = reasoning_content
            self.store.append_message(session_id, "assistant", message.get("content") or "", metadata=assistant_metadata)
            if not tool_calls:
                if force_classify:
                    raise AgentProtocolError("本轮图片任务未收到 classify_car 工具调用")
                answer = message.get("content") or "没有生成可展示的回答。"
                state = self.store.get_session(session_id)
                return self._response(session_id, answer, state, trace)
            if force_classify and tool_calls[0].get("function", {}).get("name") != "classify_car":
                raise AgentProtocolError("图片任务的第一条工具调用必须是 classify_car")
            force_classify = False
            stopped = False
            for tool_call in tool_calls:
                name = tool_call.get("function", {}).get("name")
                call_id = tool_call.get("id")
                start = time.perf_counter()
                args: dict = {}
                try:
                    if stopped:
                        raise AgentProtocolError("识别未成功或为 unknown，本批次后续工具已停止")
                    args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                    valid_args = self._validate_args(name, args, self.store.get_session(session_id))
                    result = self._execute(name, valid_args, session_id)
                    status = "success"
                    model_result = result
                except Exception as exc:
                    valid_args = args if isinstance(args, dict) else {}
                    result = {"ok": False, "error": str(exc)}
                    status = "failed"
                    model_result = result
                duration = int((time.perf_counter() - start) * 1000)
                summary = self._trace_result(name, result) if status == "success" else {"error": result["error"]}
                item = self.store.add_tool_run(session_id, name or "unknown", status, valid_args, summary, duration, call_id)
                item.update({"arguments": valid_args, "result": summary})
                trace.append(item)
                self.store.append_message(session_id, "tool", json.dumps(model_result, ensure_ascii=False), metadata={"tool_call_id": call_id, "name": name})
                state = self.store.get_session(session_id)
                classification = state.get("classification") or {}
                if name == "classify_car" and (status == "failed" or classification.get("label") == "unknown" or classification.get("rejected")):
                    stopped = True
            # 每个 tool_call 都必须有对应结果，保证拒识后的下一轮会话仍符合 API 协议。
            if stopped:
                answer = "未识别为本组支持的车型或图片识别失败，系统已停止后续车型工具。请换用车身完整、光线清晰的照片后重试。"
                self.store.append_message(session_id, "assistant", answer)
                return self._response(session_id, answer, self.store.get_session(session_id), trace)
        raise AgentProtocolError("工具调用轮次超过安全上限，请稍后重试")

    def _response(self, session_id: str, answer: str, state: dict, trace: list[dict]) -> dict:
        return {"session_id": session_id, "answer": answer, "classification": state.get("classification"), "design_language": state.get("design_language"), "views": state.get("views", []), "board_url": state.get("board_url"), "trace": trace}

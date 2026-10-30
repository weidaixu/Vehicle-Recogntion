"""一次有界的真实 DeepSeek 验证；使用独立验收数据库，不改用户档案。"""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import load_project_env
load_project_env()
from backend.agent_runtime import AgentRuntime
from backend.session_store import SessionStore
from agent_tools import VehicleClassifier


def main():
    target = ROOT / "output/course-audit"
    target.mkdir(exist_ok=True)
    evidence = json.loads((target / "evidence.json").read_text(encoding="utf-8"))
    failures = {e["image"] for e in evidence["errors"]}
    image = next(p for p in (ROOT / "prepared_final/val").glob("*/*.jpg") if p.parent.name != "unknown" and str(p.relative_to(ROOT)) not in failures)
    catalog = {r["id"]: r for r in json.loads((ROOT / "cls_info/class_info.json").read_text(encoding="utf-8"))}
    runtime = AgentRuntime(store=SessionStore(target / "acceptance.sqlite"), classifier=VehicleClassifier(ROOT / "output/model.pt"), catalog=catalog, max_rounds=7)
    session = "acceptance-" + uuid.uuid4().hex
    result = {"session_id": session, "image": str(image.relative_to(ROOT)), "transport": "real DeepSeek API"}
    try:
        first = runtime.run(session, "请识别这张图片，再调用 query_car_info 查询车型资料。只完成这两个工具并介绍结果。", "acceptance.jpg", image)
        result["first"] = first
        print("first: " + ", ".join(t["tool"] + ":" + t["status"] for t in first["trace"]), flush=True)
        second = runtime.run(session, "请沿用刚才的车型：先调用 query_car_info，再 generate_design_language，最后 save_vehicle_archive，标题为课程验收档案。不要搜索图片或建立图板。")
        result["second"] = second
        result["archives"] = runtime.store.search_archives("课程验收档案")
        result["passed"] = (first["trace"][0]["tool"] == "classify_car" and len([t for t in second["trace"] if t["status"] == "success"]) >= 3 and bool(result["archives"]))
    except Exception as exc:
        result["passed"] = False
        result["error"] = str(exc)
    (target / "live-agent.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "error": result.get("error"), "session_id": session}, ensure_ascii=False))


if __name__ == "__main__":
    main()

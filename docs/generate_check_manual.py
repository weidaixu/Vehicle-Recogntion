from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "DriveScope汽车视觉智能体老师检查说明书.docx"
METRICS = ROOT / "output" / "experiments" / "finetune_stage2" / "metrics.json"
CONFIG = ROOT / "output" / "experiments" / "finetune_stage2" / "config.json"


def set_cell_shading(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shading = props.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        props.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_borders(cell, color: str = "D9D9D9") -> None:
    props = cell._tc.get_or_add_tcPr()
    borders = props.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        props.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        item = borders.find(qn(tag))
        if item is None:
            item = OxmlElement(tag)
            borders.append(item)
        item.set(qn("w:val"), "single")
        item.set(qn("w:sz"), "4")
        item.set(qn("w:space"), "0")
        item.set(qn("w:color"), color)


def set_run_font(run, name: str = "Microsoft YaHei", size: float | None = None, bold: bool | None = None, color: str | None = None) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_text(doc: Document, text: str = "", style: str | None = None, align=None):
    p = doc.add_paragraph(style=style)
    if text:
        run = p.add_run(text)
        set_run_font(run)
    if align is not None:
        p.alignment = align
    return p


def add_code(doc: Document, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.right_indent = Inches(0.18)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.05
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F2F4F3")
    pPr.append(shd)
    run = p.add_run(text)
    set_run_font(run, "Consolas", 9.2)
    return p


def add_bullets(doc: Document, items: list[str]):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(item)
        set_run_font(run)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    table.style = "Table Grid"
    for index, text in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = ""
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_shading(cell, "27332F")
        set_cell_borders(cell)
        run = cell.paragraphs[0].add_run(text)
        set_run_font(run, size=9.5, bold=True, color="FFFFFF")
        if widths:
            cell.width = Inches(widths[index])
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        for index, text in enumerate(row):
            cell = cells[index]
            cell.text = ""
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_borders(cell)
            if row_index % 2:
                set_cell_shading(cell, "F4F6F5")
            run = cell.paragraphs[0].add_run(str(text))
            set_run_font(run, size=9.2)
            if widths:
                cell.width = Inches(widths[index])
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_heading(doc: Document, text: str, level: int):
    p = doc.add_paragraph(style=f"Heading {level}")
    run = p.add_run(text)
    set_run_font(run, size=16 if level == 1 else 12.2, bold=True, color="000000")
    return p


def load_project_facts() -> dict:
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    train_count = sum(1 for p in (ROOT / "prepared_final" / "train").rglob("*") if p.is_file())
    val_count = sum(1 for p in (ROOT / "prepared_final" / "val").rglob("*") if p.is_file())
    classes = [line.strip() for line in (ROOT / "classes.txt").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return {
        "metrics": metrics,
        "config": config,
        "train_count": train_count,
        "val_count": val_count,
        "class_count": len(classes),
        "model_class_count": len(classes) + 1,
    }


def build() -> Path:
    facts = load_project_facts()
    metrics = facts["metrics"]
    config = facts["config"]

    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)

    for name, size, bold in (("Normal", 10.2, False), ("Title", 25, True), ("Heading 1", 16, True), ("Heading 2", 12.2, True)):
        style = doc.styles[name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.bold = bold
        style.font.color.rgb = RGBColor(0, 0, 0)
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.28

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("DriveScope 汽车视觉智能体老师检查说明书")
    set_run_font(run, size=24, bold=True, color="000000")
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("项目定位 车型识别 真实工具调用 视觉档案")
    set_run_font(run, size=11, color="52605A")
    add_text(doc, f"检查版日期 {date.today().isoformat()}  适用目录 E:/课程设计", align=WD_ALIGN_PARAGRAPH.CENTER)
    add_text(doc, "本说明书用于老师现场检查和项目答辩。重点说明项目能做什么、如何运行、哪些结果已经验证，以及哪些内容仍依赖教师测试集或 DeepSeek 账户条件。")

    add_heading(doc, "1 项目结论", 1)
    add_text(doc, "DriveScope 是一个车展车型视觉研究与档案助手。用户上传车辆图片并提出自然语言任务，后端由 DeepSeek 负责规划工具调用，自训练 ResNet18 负责车型识别，FastAPI 负责校验与执行，React 工作台负责展示结果、历史档案和工具轨迹。当前本地核心链路、后端测试、前端测试和生产构建均已通过；教师指定测试集尚未放入项目，因此不伪造最终 predictions.csv。")
    add_table(doc, ["检查项", "当前结果", "证据"], [
        ["分类类别", "50 个目标车型 + unknown，共 51 类", "classes.txt、prepared_final、output/model.pt"],
        ["正式模型", "ResNet18，GPU 训练产物，当前服务读取 output/model.pt", "output/experiments/finetune_stage2/config.json"],
        ["验证指标", f"Macro-F1 {metrics['macro_f1']:.4f}，Accuracy {metrics['accuracy']:.4f}", "output/experiments/finetune_stage2/metrics.json"],
        ["拒识策略", f"阈值 {metrics['threshold']:.2f}，unknown Recall {metrics['unknown_recall']:.4f}", "验证集阈值扫描结果"],
        ["自动化测试", "后端 27 项通过，前端 17 项通过", "pytest 与 frontend/node_modules/.bin/vitest.cmd"],
        ["生产构建", "Vite 构建通过，输出到 build-output", "frontend/package.json、build-output"],
    ], [1.25, 2.7, 2.6])

    add_heading(doc, "2 项目目标与演示闭环", 1)
    add_text(doc, "项目把一次拍照任务扩展为可继续研究的工作流：发现车辆，识别车型，理解设计，检索多视角资料，生成设计板，保存档案，最后可以按历史继续追问。它不是只返回一个分类标签，而是把识别结果、来源信息、工具执行状态和会话上下文一起保存。")
    add_table(doc, ["步骤", "用户操作", "系统行为", "可检查结果"], [
        ["1", "上传车辆图片并输入任务", "创建 session，注册受控 image_ref", "页面显示会话和图片任务"],
        ["2", "等待首次识别", "DeepSeek 首个 tool_call 必须是 classify_car", "工具轨迹出现 classify_car"],
        ["3", "继续要求研究车型", "模型按需调用资料、设计语言和视觉档案工具", "结果区与轨迹同步更新"],
        ["4", "要求保存或生成图板", "后端校验 class_id 与会话识别结果，再落库或生成文件", "档案记录、JPG 和 JSON manifest"],
        ["5", "历史检索与追问", "从 SQLite 恢复上下文，无需再次上传图片", "历史列表和连续对话"],
    ], [0.45, 1.65, 3.2, 1.25])

    add_heading(doc, "3 整理后的目录说明", 1)
    add_text(doc, "项目运行所需的源码和数据仍保留在原路径，避免改变 import、训练脚本和启动命令。说明书与检查入口集中放在 docs，运行产物集中在 output，前端构建产物集中在 build-output。缓存和系统导入目录不作为提交内容。")
    add_table(doc, ["目录或文件", "用途", "老师检查建议"], [
        ["README.md", "项目总览、启动命令、指标边界", "先看这里，了解项目入口"],
        ["backend/", "FastAPI、AgentRuntime、SQLite、工具路由", "重点看 agent_runtime.py 和 session_store.py"],
        ["frontend/", "React、Three.js、测试与构建配置", "重点看 src/App.tsx 与 ToolRail.tsx"],
        ["train.py、data_pipeline.py", "数据合同、训练、评估、批量预测", "检查 50 类加 unknown 的训练逻辑"],
        ["prepared_final/", "当前正式训练与验证数据", "不需要逐张打开，查看类别目录即可"],
        ["output/experiments/", "各阶段模型、配置、指标、混淆矩阵", "查看 final metrics.json"],
        ["output/model.pt", "当前服务实际加载的模型文件", "说明书中的正式模型产物"],
        ["docs/", "计划、规格、项目视觉资料与本说明书", "本文件是现场检查版"],
        ["build-output/", "Vite 生产构建结果", "可用于静态页面检查"],
        ["train/、val/", "教师原始 827 类数据", "原始数据，不建议移动或改名"],
    ], [1.55, 3.0, 2.0])

    add_heading(doc, "4 数据准备与模型训练", 1)
    add_text(doc, "原始 train 和 val 各包含教师数据的 827 个类别目录。data_pipeline.py 根据 train 与 val 同时存在且样本充足的条件，稳定选择 50 个四位 ID 类别，并从未选类别中抽样构造 unknown。classes.txt 只保存 50 个确定类别；unknown 作为 ImageFolder 的第 51 个模型类别写入 prepared_final/label_map.json。")
    add_table(doc, ["数据项", "当前值", "说明"], [
        ["目标类别", "50", "classes.txt 中 50 行，四位数字、唯一、升序"],
        ["模型类别", "51", "50 个确定车型加 unknown"],
        ["prepared_final/train", str(facts["train_count"]), "当前正式训练集图片数"],
        ["prepared_final/val", str(facts["val_count"]), "当前正式验证集图片数"],
        ["训练架构", config.get("architecture", "resnet18"), "当前 final experiment 配置"],
        ["训练设备", config.get("device", "unknown"), "保存于训练配置"],
        ["图像尺寸", "224 x 224", "ResNet18 分支使用的输入尺寸"],
    ], [1.65, 1.65, 3.2])
    add_text(doc, "当前正式实验使用两阶段迁移学习：先在教师车辆数据上训练 ResNet18 的阶段性模型，再以较低学习率继续微调，并使用 balanced loss 处理类别分布。最终模型的拒识阈值不是凭感觉设置，而是在验证集上扫描不同阈值，以 Macro-F1 最大为选择依据。")
    add_code(doc, ".\\.venv\\Scripts\\python.exe -m pytest -q\n\n# 仅在需要重新训练时使用，当前检查不要求重新训练\n.\\.venv\\Scripts\\python.exe train.py --data prepared_final --architecture resnet18 --resume output\\experiments\\finetune_stage1\\best_model.pt --balanced-loss --epochs 8 --batch 48 --lr 0.00002")

    add_heading(doc, "5 真实 Tool Calling 链路", 1)
    add_text(doc, "本项目的关键点是 DeepSeek 负责调用工具，而不是前端先调用分类接口再把结果包装成智能体。新图片任务会把受控 image_ref 放进当前会话，并把 tool_choice 设为 classify_car。后端收到 tool_calls 后，校验工具名、参数和当前会话状态，执行本地模型，再以 role=tool 和原 tool_call_id 把结果回传给 DeepSeek。没有 tool_calls 时才结束本轮并返回最终文本。")
    add_table(doc, ["工具", "作用", "安全约束"], [
        ["classify_car", "调用本地 51 类视觉模型", "只能使用当前 session 的 image_ref"],
        ["query_car_info", "读取 class_info.json 车型资料", "class_id 必须等于当前识别结果"],
        ["search_vehicle_views", "本地或 Wikimedia 多视角资料", "limit 限制为 1 到 12"],
        ["generate_design_language", "生成结构化设计语言", "固定字段并保留 limitations"],
        ["build_design_board", "生成 JPG 图板和 JSON 清单", "必须先有设计语言"],
        ["save_vehicle_archive", "保存可检索研究档案", "必须有识别和设计语言"],
        ["search_archive_history", "检索历史档案", "查询长度和数量均受限"],
    ], [1.8, 3.1, 1.6])
    add_code(doc, "新图片：tool_choice = {type: function, function: {name: classify_car}}\n后续追问：tool_choice = auto\n消息链：assistant.tool_calls -> 后端执行 -> role=tool -> DeepSeek 继续判断")
    add_text(doc, "如果识别为 unknown 或 confidence 低于阈值，后端立即停止确定车型相关工具，并向用户说明需要更换照片。这一规则由程序强制执行，不依赖模型是否自行遵守。图片字节不发送给 DeepSeek，API Key 只从后端环境变量读取。")

    add_heading(doc, "6 后端接口与持久化", 1)
    add_table(doc, ["方法", "路径", "用途"], [
        ["GET", "/api/health", "基础健康检查"],
        ["GET", "/api/status", "模型、类别数、Macro-F1、Key 配置和 WebGL 资产状态"],
        ["POST", "/api/agent/upload", "上传图片并启动首轮 classify_car"],
        ["POST", "/api/agent", "在已有 session 中发送文本追问"],
        ["GET", "/api/session/{session_id}", "查看会话消息、上下文和工具运行记录"],
        ["GET", "/api/cars/{class_id}", "查询课程车型资料"],
        ["GET", "/api/vehicle-views/{class_id}", "查询带来源信息的多视角资料"],
        ["POST", "/api/design-board", "生成设计板"],
        ["GET", "/api/archives", "检索历史档案"],
    ], [0.8, 2.5, 3.2])
    add_text(doc, "SQLite 数据库位于 output/vehicle_agent.sqlite。主要记录包括 sessions、messages、session_images、tool_runs 和 vehicle_archives。数据库是本地运行数据，不应提交 API Key 或个人信息；检查时可以用它证明会话、工具轨迹和档案具备持久化能力。")

    add_heading(doc, "7 前端页面与视觉设计", 1)
    add_text(doc, "前端位于 frontend，使用 React、TypeScript、Vite、Three.js、React Three Fiber、Framer Motion 和 lucide-react。主工作台包含图片与任务输入、对话区、结果区、工具轨迹和历史档案。首页保留明亮清晨的汽车展厅氛围，背景通过深度层、视差和轻量粒子形成 3D 感；核心业务不依赖 WebGL，减少动态效果设置会关闭循环动画。")
    add_table(doc, ["前端区域", "可展示内容"], [
        ["状态栏", "类别数、Macro-F1、DeepSeek 配置状态"],
        ["聊天区", "自然语言任务、连续追问、最终中文回答"],
        ["工具轨迹", "真实工具名、状态、参数摘要、结果摘要和耗时"],
        ["研究结果", "车型名、Top 3、置信度、设计语言和限制说明"],
        ["视觉档案", "本地或公开素材、来源、许可证和设计板"],
        ["历史档案", "保存后的车型研究记录和继续追问入口"],
    ], [2.0, 4.5])
    add_code(doc, "cd frontend\n# 已安装依赖时直接运行\n..\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\bin\\fallback\\pnpm.cmd dev\n\n# 生产构建\n..\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\bin\\fallback\\pnpm.cmd build")
    add_text(doc, "如果 pnpm 试图在无交互终端清理 node_modules，老师现场可直接使用现有 frontend/node_modules/.bin/vite.cmd 或 vitest.cmd；这不改变项目源码。浏览器访问地址通常为 http://127.0.0.1:5173。")

    add_heading(doc, "8 老师现场演示流程", 1)
    add_bullets(doc, [
        "先打开 README.md 和本说明书，说明项目定位是车展车型视觉研究与档案助手。",
        "启动后端，打开 /api/health 和 /api/status，展示服务健康、51 类、Macro-F1 和前端资产状态。",
        "启动前端，上传一张车身完整、光线清晰的图片，输入“识别车型并分析设计语言”。",
        "重点展示工具轨迹：第一项必须是 classify_car，而不是前端直接调用 /api/classify。",
        "继续输入“查找这辆车的多视角资料并生成设计板”，展示工具链、来源信息和下载链接。",
        "输入“保存这辆车到历史档案”，刷新或重新打开历史区，证明 session 和 SQLite 持久化。",
        "最后可用不清晰或非目标车辆演示 unknown/低置信度中断，说明系统不会把不确定结果继续当成确定车型。",
    ])

    add_heading(doc, "9 验证记录与边界", 1)
    add_text(doc, "本次整理前已执行项目级验证：后端 pytest 27 项全部通过，耗时约 45 秒；前端 Vitest 6 个测试文件、17 项全部通过；前端生产构建配置已指向根目录 build-output。上述结果是本机当前 checkout 的验证证据，不代表任何未运行环境的结果。")
    add_table(doc, ["已完成并验证", "当前边界", "现场说明"], [
        ["50 类加 unknown 数据合同", "教师测试集尚未提供", "不能提前生成真实 predictions.csv"],
        ["ResNet18 验证集指标", "验证集不等同于教师测试成绩", f"Macro-F1 {metrics['macro_f1']:.4f} 只用于当前验证集"],
        ["真实 Tool Calling 协议测试", "DeepSeek 实时调用依赖 Key、网络和余额", "无 Key 时先做本地测试，不伪造云端结果"],
        ["本地素材与离线回退", "Wikimedia 结果随网络变化", "展示来源字段，网络失败仍可用本地图片"],
        ["源码级上传和前端测试", "真实浏览器文件选择需现场操作", "浏览器安全策略不等于代码缺陷"],
    ], [2.2, 2.5, 1.8])

    add_heading(doc, "10 提交与检查清单", 1)
    add_bullets(doc, [
        "README.md：项目总览、启动、测试、边界。",
        "DriveScope汽车视觉智能体老师检查说明书.docx：本次检查版说明书。",
        "classes.txt、selected_classes.json、data_pipeline.py：类别选择和数据准备证据。",
        "train.py、output/model.pt、output/experiments/：训练、模型和指标证据。",
        "backend/ 和 frontend/：应用源码。",
        "tests/ 与 frontend/src/**/*.test.*：自动化测试。",
        "教师测试集到位后，再使用 train.py 的 --predict-dir 生成 predictions.csv。",
        "检查提交目录中不包含 DEEPSEEK_API_KEY、二维码、Token 或其他个人凭据。",
    ])
    add_heading(doc, "附录 关键文件速查", 1)
    add_table(doc, ["文件", "讲解重点"], [
        ["backend/agent_runtime.py", "Tool Calling 循环、首步 classify_car、参数校验、unknown 中断"],
        ["backend/session_store.py", "SQLite 表结构、消息、图片引用、工具运行和档案"],
        ["backend/deepseek_client.py", "DeepSeek 模型调用、Key 读取和错误处理"],
        ["frontend/src/App.tsx", "聊天工作台、状态、结果和历史档案"],
        ["frontend/src/components/ToolRail.tsx", "工具轨迹展示"],
        ["data_pipeline.py", "50 类选择、unknown 抽样、哈希去重"],
        ["train.py", "模型、训练、评估、阈值和批量预测"],
        ["README.md", "最短启动路径和项目边界"],
    ], [2.55, 3.95])

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("DriveScope 汽车视觉智能体老师检查说明书")
    set_run_font(run, size=8.5, color="6A746E")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())

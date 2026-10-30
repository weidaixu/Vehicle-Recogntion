from pathlib import Path
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

OUT = Path("output/DriveScope汽车视觉智能体实训讲解手册.docx")
# The previous capture shows the retired stage-based UI; omit it until a fresh
# browser capture of the chat workspace is available.
SCREENSHOT = Path("output/drivescope-agent-current.png")
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.top_margin = sec.bottom_margin = Inches(.72)
sec.left_margin = sec.right_margin = Inches(.82)
for name, size, bold in [("Normal", 10.5, False), ("Title", 25, True), ("Heading 1", 17, True), ("Heading 2", 12.5, True)]:
    style = doc.styles[name]
    style.font.name = "Microsoft YaHei"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    style.font.size = Pt(size); style.font.bold = bold; style.font.color.rgb = RGBColor(0, 0, 0)
doc.styles["Normal"].paragraph_format.space_after = Pt(7)
doc.styles["Normal"].paragraph_format.line_spacing = 1.3

def para(text="", style=None, align=None):
    p = doc.add_paragraph(style=style)
    if text: p.add_run(text)
    if align is not None: p.alignment = align
    return p

def bullets(items):
    for item in items: doc.add_paragraph(item, style="List Bullet")

def shade(cell, color):
    shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), color); cell._tc.get_or_add_tcPr().append(shd)

def table(headers, rows, widths):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"
    t.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for i, text in enumerate(headers):
        c=t.rows[0].cells[i]; c.text=text; shade(c,"30332E")
        for r in c.paragraphs[0].runs: r.font.color.rgb=RGBColor(255,255,255); r.font.bold=True
    for n,row in enumerate(rows):
        cells=t.add_row().cells
        for i,text in enumerate(row):
            cells[i].text=str(text); cells[i].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; cells[i].width=Inches(widths[i])
            if n%2: shade(cells[i],"F3F3F1")
    para(); return t

para("DriveScope 汽车视觉智能体实训讲解手册","Title",WD_ALIGN_PARAGRAPH.CENTER)
para("车型识别 设计语言 多视角视觉档案",None,WD_ALIGN_PARAGRAPH.CENTER)
para("本手册面向课程验收、现场演示和答辩讲解。项目以 51 类自训练视觉模型为入口，使用 DeepSeek V4 Flash 生成结构化汽车设计语言，并从本地数据集与 Wikimedia Commons 建立带来源信息的多视角视觉档案。最终系统采用 React、Three.js 与 FastAPI，实现可运行、可追溯、可扩展的完整智能体应用。")

para("1 项目主题与完成范围","Heading 1")
para("项目主题为车展车型视觉研究与档案助手。目标用户是车展观众、汽车爱好者、汽车设计学生和车型内容创作者。业务闭环是发现车辆、识别车型、理解设计、收集多视角资料、保存档案、历史检索与继续追问。用户上传汽车照片并输入自然语言任务后，DeepSeek 先通过真实 Function Calling 发起 classify_car；后续工具由模型根据返回结果决定，程序记录每次参数、结果、状态和耗时。")
table(["核心功能","输入","输出"],[["车型识别","用户上传的车辆照片","类别 ID、车型名、Top 3、置信度、unknown 状态"],["设计语言","识别结果、车型资料、用户关注点","比例、灯组、曲面、空气动力学、品牌特征"],["视觉档案","车型 ID","本地与公开授权图片、作者、许可证、来源页"],["设计图板","识别结果、设计语言、多视角图像","1800×1200 JPG 与 JSON 来源清单"]],[1.25,1.8,3.5])

para("2 与任务书要求的对应关系","Heading 1")
table(["任务书要求","项目实现","证据位置"],[["50 个车型加 unknown","classes.txt 为 50 行，模型输出为 51 类","classes.txt 和 output/model.pt"],["自行训练视觉模型","ResNet18 在教师车辆数据上完成两阶段真实微调","train.py 和 output/model.pt"],["真实工具调用","七个工具由 DeepSeek 响应驱动，首轮强制 classify_car","backend/agent_runtime.py"],["三工具以上连续调用","识别后可继续查询资料、生成设计语言、检索视图、建板和保存档案","POST /api/agent/upload"],["多轮 Session","SQLite 保存图片引用、消息、识别、设计分析、视图、图板和档案","backend/session_store.py"],["Web 展示与异常处理","React 聊天工作台展示真实轨迹、历史档案和拒识状态","frontend/src"]],[1.55,2.35,2.65])

para("3 系统架构","Heading 1")
para("前端负责交互与呈现，后端负责模型推理、密钥保护、联网检索和图板生成。API Key 只从后端环境变量读取，不会进入浏览器代码。Three.js 场景与业务状态隔离，即使 WebGL 不可用，识别等核心功能仍能继续工作。")
para("调用关系不是后端写死的阶段变量：新图片任务的第一轮请求使用工具选择约束，要求 DeepSeek 返回 classify_car；随后每轮把工具结果回传给 DeepSeek，由模型决定是否查询资料、生成设计语言、检索多视角、建立图板或保存档案。程序端仍会校验 class_id、image_ref、阈值和数量，并在 unknown 或低置信度时强制停止。")
table(["层","技术","职责"],[["交互层","React 19 TypeScript Vite","上传、状态、结果、档案、下载"],["沉浸视觉","Three.js React Three Fiber Framer Motion","景深视差、HUD、扫描光带、状态动效"],["服务层","FastAPI Pydantic","接口、校验、会话与错误码"],["视觉模型","PyTorch Pillow","51 类推理、Top 3、低置信度拒识"],["智能分析","DeepSeek V4 Flash","严格 JSON 设计语言输出"],["素材与导出","本地数据 Wikimedia Commons Pillow","授权资料检索与图板生成"]],[1.15,2.15,3.25])

para("4 数据与模型训练","Heading 1")
para("原始数据包含 827 个类别。data_pipeline.py 依据训练集和验证集可用性固定选择 50 类，并从未选类别抽取 unknown。最终 prepared_final 数据集包含 6270 张训练图片和 2094 张验证图片；unknown 训练集为 400 张、来源于 311 个组外车型，unknown 验证集为 150 张、来源于 136 个组外车型。程序使用 SHA-256 检查并排除训练与验证内容重复，确保验证集不泄漏。")
para("训练命令")
para(".\\.venv\\Scripts\\python.exe train.py --data prepared_final --architecture resnet18 --resume output/experiments/baseline_clean/model.pt --freeze-backbone --unfreeze-last --balanced-loss --epochs 12 --batch 64 --lr 0.0001")
para("本次使用官方 ImageNet 预训练 ResNet18 作为初始化，在教师车辆数据上进行两阶段迁移学习：先解冻最后残差阶段训练 12 轮，再解冻完整主干，以 2e-5 学习率继续微调并提前停止。干净验证集基线 Macro-F1 为 0.4645；最终原始 argmax Macro-F1 为 0.8446。验证集扫描得到拒识阈值 0.26，最终 Macro-F1 为 0.8480、Accuracy 为 0.8080、unknown Recall 为 0.6533、已知类误拒率为 0.1157。")

para("5 车型识别与低置信度策略","Heading 1")
para("后端接受最大 15 MB 图片，并验证文件是否能由 Pillow 解码。VehicleClassifier 可直接接收 PIL Image，也兼容 Streamlit UploadedFile，因此已修复 UploadedFile 没有 convert 方法的报错。模型输出 Top 3 和 confidence；若模型直接预测 unknown，或最高置信度低于验证集确定的 0.26 阈值，label 返回 unknown，raw_label 保留原始候选。")
para("前端会明确显示拒识提示，并停止设计语言、视觉档案和设计板工具链，要求用户重新拍摄。这样符合任务书关于 unknown 和低置信度不得继续按确定车型执行的要求。")

para("6 DeepSeek 设计语言","Heading 1")
para("外层 Agent 使用 DeepSeek 的 Chat Completions 工具调用协议；工具定义包含 classify_car、query_car_info、search_vehicle_views、generate_design_language、build_design_board、save_vehicle_archive 和 search_archive_history。图片不发送给 DeepSeek，消息中最多出现服务端生成的受控 image_ref。generate_design_language 工具读取识别类别和 class_info.json 中的车型资料，并要求固定 JSON 字段：summary、proportions、lighting_signature、surface_language、aerodynamics、brand_cues 和 limitations。后端校验返回结构；Key 缺失返回 503，供应商失败返回 502。")
para("运行前在本机设置 DEEPSEEK_API_KEY。不要把密钥写进代码、截图、提交文件或浏览器环境变量。实时调用可能产生费用，因此验收前应先确认账户额度。")

para("7 多视角视觉档案与版权","Heading 1")
para("系统优先读取 train 和 val 中同类别的图片，因此离线时也能完成档案。网络可用时，再通过 Wikimedia Commons API 搜索补充图片。网络条目只有在返回明确许可证信息时才进入档案，并展示作者、许可证名称、许可证链接和原始文件页。")
bullets(["课程数据集图片标记为仅用于课程实训，不自动声明商业授权。","Wikimedia 图片保留 source_page 和 license_url，设计板旁应保留来源清单。","网络检索失败时自动回退本地图片，不影响核心流程。"])

para("8 前端设计与交互","Heading 1")
para("背景使用用户提供的保时捷照片，校正为横屏。色彩取自照片本身：碳黑、雾山灰、钛银、晨光白和尾灯红。WebGL 将照片拆分为远山、中景、地面和车辆四个深度层，各层按不同速度响应鼠标位置，并叠加透视倾斜、近景粒子、尾灯光轨和镜头呼吸。识别与生成期间会提升视差、粒子和速度线强度；窄屏设备保留低强度景深，prefers-reduced-motion 开启后关闭循环动态。")
if SCREENSHOT.exists():
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(SCREENSHOT),width=Inches(6.65))
    para("图 1 DriveScope 桌面首屏实测截图",None,WD_ALIGN_PARAGRAPH.CENTER)

para("9 启动方法","Heading 1")
para("后端终端")
para(".\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000")
para("前端终端")
para("cd frontend\npnpm install\npnpm dev")
para("浏览器访问 http://127.0.0.1:5173。当前 React 页面提供图片与自然语言任务、连续追问、识别结果、设计语言、视觉档案、历史检索和真实工具轨迹。生产构建使用 pnpm build，输出到项目根目录 build-output；当前唯一 Web 入口为 FastAPI 与 React/Vite。")

para("10 演示流程","Heading 1")
bullets(["打开首页，说明 51 类模型状态、验证集 Macro-F1 和 DeepSeek 配置状态。","上传一张车展照片并输入自然语言任务，观察 Agent 的首个 classify_car 工具调用。","查看右侧工具轨迹中的参数摘要、结果摘要、状态和耗时。","继续追问“把刚才这辆车保存到档案”，验证同一 Session 不需重新上传图片。","展示车型资料、设计语言、多视角图片及许可证信息。","打开历史档案，检索刚刚保存的车型，并查看设计板链接。","使用 unknown 或低置信度图片演示程序端中断，不继续按确定车型执行。"])

para("11 接口速查","Heading 1")
table(["方法","路径","作用"],[["GET","/api/status","模型、类别数、Macro F1、DeepSeek 和 WebGL 资产状态"],["POST","/api/agent/upload","保存图片引用，并由 Agent 首轮发起 classify_car"],["POST","/api/agent","同一 Session 的文本追问"],["GET","/api/session/{id}","读取消息、上下文和工具运行记录"],["GET","/api/archives?q=","历史档案检索"],["GET","/api/vehicle-views/{id}","检索多视角视觉素材"],["POST","/api/design-board","生成图板与来源清单"]],[.8,2.45,3.25])

para("12 测试与已知边界","Heading 1")
para("当前自动化测试覆盖状态接口、图片上传校验、车型目录、DeepSeek 结构化解析、多视角离线回退、设计板生成、真实工具调用循环、首轮 image_ref 约束、unknown 强制中断、Session 持久化、历史档案接口和前端聊天工作台。最近一次回归为后端 27 项、前端 11 项全部通过，生产构建也通过。")
bullets(["当前没有教师指定测试目录，因此尚不能生成最终提交版 predictions.csv；收到 test 目录后运行现有批量推理程序。","最终验证集 Macro-F1 为 0.8480，但 unknown 的来源分布与教师测试集可能不同，不能将验证成绩等同于测试成绩。","DeepSeek 实时结果依赖本机 Key、网络和账户额度；本次未擅自发送付费请求，现场演示前需由用户确认额度。","浏览器自动化上传本地文件受浏览器安全策略限制；代码级上传接口和前端测试已覆盖，真实浏览器上传需在用户浏览器中手动选择图片。","Wikimedia 搜索结果随网络和关键词变化，设计板仍可完全依赖本地图片生成。"])

para("13 提交清单","Heading 1")
bullets(["classes.txt 和 selected_classes.json","data_pipeline.py、train.py、agent_tools.py","backend 与 frontend 全部源码","output/model.pt 与真实指标","测试文件与测试结果截图","DriveScope 实训讲解手册","教师测试集到位后生成的 predictions.csv","不包含任何 API Key 或账户凭据"])

footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER; footer.add_run("DriveScope 汽车视觉智能体实训讲解手册")
OUT.parent.mkdir(exist_ok=True); doc.save(OUT); print(OUT)

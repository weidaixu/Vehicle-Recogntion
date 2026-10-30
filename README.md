# DriveScope 汽车视觉研究与档案助手

公开仓库保存源码、配置示例及不含个人信息的文档。数据集、模型权重、运行日志和含学号的课程报告留在本地；运行前需按下文准备数据与权重，并配置自己的密钥。

DriveScope 面向车展观众、汽车爱好者、汽车设计学生和车型内容创作者，把“发现车辆 → 识别车型 → 理解设计 → 收集多视角资料 → 保存档案 → 历史检索与继续追问”串成一个可复核的业务流程。

## 当前实现

- 50 个目标车型 + `unknown` 的自训练 ResNet18，输出 Top-3、confidence 和验证集拒识阈值。
- DeepSeek `deepseek-v4-flash` 服务端 Function/Tool Calling 循环。图片只在本地视觉工具中处理；模型只接收受控 `image_ref`，不接收图片字节或 data URL。
- 七个真实工具：`classify_car`、`query_car_info`、`search_vehicle_views`、`generate_design_language`、`build_design_board`、`save_vehicle_archive`、`search_archive_history`。
- 新图片会强制要求 DeepSeek 的第一条响应发起 `classify_car`；后续工具由模型响应驱动，程序负责参数校验、工具执行、失败记录、耗时记录和最大轮次保护。
- `unknown` 或低置信度会在后端强制中断，不会继续按某个确定车型查询、建板或保存。
- 同一 `session_id` 持久化图片引用、消息历史、识别结果、设计分析、视觉档案、设计板和档案记录；文本追问无需再次上传图片。
- React 聊天主界面支持图片+自然语言任务、连续追问、设计语言、多视角资料、历史档案和真实工具轨迹；保留鼠标跟随 3D 景深赛车氛围并尊重减少动态效果设置。

## 关键接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/api/status` | 模型状态、51 类、Macro-F1、DeepSeek 配置状态 |
| `POST` | `/api/agent/upload` | 保存图片引用，并由 Agent 首轮发起 `classify_car` |
| `POST` | `/api/agent` | 在同一 Session 中发送文本追问 |
| `GET` | `/api/session/{session_id}` | 查看持久化消息、上下文和工具运行记录 |
| `GET` | `/api/archives?q=` | 检索已保存车型档案 |
| `GET` | `/api/vehicle-views/{class_id}` | 获取本地/带授权元数据的多视角图片 |
| `POST` | `/api/design-board` | 生成设计板与来源清单 |

## 启动

后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

前端另开终端：

```powershell
cd frontend
pnpm install
pnpm dev -- --configLoader runner --host 127.0.0.1
```

访问 `http://127.0.0.1:5173`。如果本机已有旧 Vite 进程导致临时文件无法写入，先停止占用 5173/4173 的本项目进程，再重新启动。

DeepSeek Key 只在后端环境变量中配置：

```powershell
$env:DEEPSEEK_API_KEY="你的密钥"
```

不要把 Key 写入源码、前端变量、日志、截图、报告或数据库。实时请求可能产生费用；没有余额或没有明确授权时，只运行本地测试和假传输测试。

## 测试与构建

```powershell
cd E:\课程设计
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .\tmp\pytest-local
cd frontend
pnpm test -- --run --configLoader runner
pnpm build
```

2026-09-20 的历史回归证据见 `output/course-audit/test-results.txt`；它不代表当前环境已经重新通过。构建输出写入项目根目录 `build-output/`。

## 模型与数据边界

- `classes.txt` 保留恰好 50 行四位车型 ID，`unknown` 只作为第 51 个模型输出，不写入该文件。
- 当前 `output/model.pt` 是已有自训练 ResNet18 产物，保留训练配置、实验日志、混淆矩阵和每类指标。最新核验重新推理全部验证图片，证据保存在 `output/course-audit/evidence.json`。
- 验证集校准拒识阈值为 `0.26`，最终验证集 Macro-F1 为 `0.8479867573`，Accuracy 为 `0.8080229226`，unknown Recall 为 `0.6533333333`。这些是验证结果，不等同于教师测试成绩。
- 当前工作区已有 `测试集/test_images`，但模型验证集指标不等于教师平台成绩。批量提交文件应以教师平台当前要求为准；现有 `generate_submission.py` 可生成课程测试所需预测结果，正式提交前仍须核对文件名、标签顺序和平台格式。
- 网络视觉素材只有在带作者、许可证、许可证链接和来源页时才进入结果；网络失败会回退本地数据集图片。

## 从源码安装与复验

Python 3.11 或兼容版本、Node.js 22。已有 `.venv` 时无需重新创建。首次安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
pnpm install --frozen-lockfile
```

在项目根目录复制 `.env.example` 为 `.env` 并填写自己的密钥（已有 `.env` 时保留）。服务端启动时自动加载。模型权重按任务书只在本地保存，因此源码包接收者需训练生成 `output/model.pt` 或在本地恢复自己保存的权重。

```powershell
# 用教师原始 train、val、cls_info 数据创建训练目录；只在新环境首次准备时执行
.\.venv\Scripts\python.exe data_pipeline.py --max-per-class 120 --max-val-per-class 40 --unknown-train 400 --unknown-val 150
# 可复现的全新训练入口；不自动覆盖已有最终权重
.\.venv\Scripts\python.exe train.py --architecture resnet18 --pretrained --balanced-loss --epochs 12 --out output/new_model.pt
# 重新核验当前最终权重、数据来源、划分与验证集指标
.\.venv\Scripts\python.exe scripts/audit_course.py
# 有界真实 API 验收，会产生少量 API 调用费用
.\.venv\Scripts\python.exe scripts/verify_live_agent.py
# 教师提供指定测试图片后生成最终预测
.\.venv\Scripts\python.exe train.py --out output/model.pt --predict-dir "教师测试目录" --predictions predictions.csv
# 根据最新证据生成报告与源码包，不打包真实密钥、运行数据库、数据集或权重
.\.venv\Scripts\python.exe scripts/build_course_report.py
```

批量与 Web 共用同一分类器、预处理和拒识阈值。confidence 为原始最高 softmax 概率；低于阈值输出 unknown 时仍保留该分数。批量任务拒绝空目录与重名图片，避免漏交或重复 image_id。正式提交前需补齐教师测试结果与两位成员实际分工。初始化权重的本地比对证据及历史记录局限已写入报告。

## 项目文件

- `backend/agent_runtime.py`：真实工具调用循环、工具参数校验和 unknown 中断。
- `backend/session_store.py`：SQLite Session、消息、工具运行、图片引用和档案持久化。
- `backend/routes/agent.py`、`backend/routes/archives.py`：对话、上传、Session 和历史接口。
- `frontend/src/App.tsx`、`frontend/src/components/ToolRail.tsx`：聊天工作台、结果区、历史档案和真实轨迹展示。
- `output/vehicle_agent.sqlite`：运行时本地数据；不要提交其中的任何密钥或个人数据。
- `docs/DriveScope汽车视觉智能体老师检查说明书.docx`：面向老师检查的架构、训练指标、工具调用、局限、目录和运行说明。

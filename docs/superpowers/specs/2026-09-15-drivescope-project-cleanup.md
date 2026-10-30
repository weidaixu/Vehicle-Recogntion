# DriveScope 项目保守清理与职责文档设计

## 目标

在不改变 DriveScope 当前 FastAPI + React 主流程、不重新训练模型、不删除原始课程数据和正式训练证据的前提下，移除确定无引用的历史实现、重复中间数据、旧构建和缓存；整理依赖与文档，并生成可供老师和后续维护者查阅的文件职责清单。

## 保留边界

以下内容必须保留：

- `train/`、`val/`：教师原始 827 类数据，也是多视角本地资料来源。
- `prepared_final/`：当前 50 个目标车型加 `unknown` 的正式训练与验证数据。
- `output/model.pt`、`output/experiments/`：自训练 ResNet18、配置、历史、指标、混淆矩阵和每类指标。
- `output/vehicle_agent.sqlite`：Session、消息、工具轨迹和车型档案。
- `output/session-images/`、`output/boards/`：当前业务会话引用和已生成图板，不能作为缓存删除。
- `frontend/public/assets/showroom-original.jpg`：用户指定的当前主页背景原图，不调色、不改内容。
- `backend/`、`frontend/src/` 当前运行源码，`tests/`、`test_agent_tools.py`，课程任务书、Notebook、老师检查文档。
- `.venv/` 与 `frontend/node_modules/`：当前可运行环境。只记录体积，不在本次删除，避免破坏已验证的 CUDA/PyTorch 与前端依赖。
- `build-output/`：当前 Vite 生产构建输出；清理后重新生成。

## 删除边界

只有完成相应引用迁移和测试后，才删除以下目标：

1. Python、pytest、TypeScript 缓存：根目录及源码目录内的 `__pycache__/`、`.pytest_cache/`、`*.pyc`、`frontend/tsconfig.*.tsbuildinfo`。
2. `tmp/`：测试生成的图板和临时 PDF 依赖副本；正式图板位于 `output/boards/`。
3. `frontend/dist/`：旧构建目录；当前唯一生产构建目录是根目录 `build-output/`。
4. 已取消的启动页：`frontend/src/components/intro/`、`frontend/public/assets/intro-cockpit.jpg` 以及仅供该页面使用的 `gsap` 依赖。
5. 旧背景资源 `frontend/public/assets/hero-car.jpg`：先把状态检查和 CSS 回退资源改为 `showroom-original.jpg`。
6. 根目录 `微信图片_20260909114448_263_11.jpg`：其 SHA-256 与 `frontend/public/assets/showroom-original.jpg` 完全一致，保留 public 版本后删除根目录副本。
7. `prepared/`、`prepared_clean/`：已被 `prepared_final/` 替代的中间数据。先将 `test_agent_tools.py` 和 `tests/test_classification_api.py` 的样本路径迁移至 `prepared_final/val`，运行分类和训练合同测试后再删除。
8. `.pnpm-store/`：项目根目录中的残留局部缓存；前端实际依赖位于 `frontend/node_modules/`。

本次不删除 `归档_非运行文件/` 和 `docs/历史版本/`。它们不是运行依赖，但属于已有整理记录和报告历史；除非用户另行明确授权，保守方案继续保留。

## 代码与依赖优化

- 将后端 `webgl_assets_ready` 检查改为当前背景 `frontend/public/assets/showroom-original.jpg`。
- 将 `.photo-bg` 的 CSS 回退背景改为 `showroom-original.jpg`，不改变 `<img>` 的旋转、裁切和视觉参数。
- 删除已经不参与渲染的 Intro 组件与测试，并从 `package.json`、`pnpm-lock.yaml`、`node_modules` 移除 GSAP。
- 将两个仍引用 `prepared/val` 的测试改为 `prepared_final/val`，保持同样的真实图片推理断言。
- 删除旧 Streamlit 入口 `app.py`，并从 `requirements.txt` 移除 `streamlit`。当前唯一 Web 入口为 `backend.main:app` 与 React/Vite；`agent_tools.py` 继续保留 `VehicleClassifier`，因为后端运行时依赖它。
- 保留 `build_manual.py` 和 `docs/generate_check_manual.py`：二者分别代表原讲解手册生成器与当前老师检查说明书生成器。职责清单明确两者差异，暂不合并，避免无依据改写课程文档。
- 新增 `.gitignore`，覆盖密钥文件、缓存、临时目录、依赖目录、运行时数据库图片和构建产物，避免清理后再次污染。

## 文件职责文档

创建 `docs/项目文件职责清单.md`：

- 对每个保留的代码、测试、配置、文档生成脚本和关键产物逐文件说明职责、运行时是否必需、主要依赖。
- 对 `train/`、`val/`、`prepared_final/` 和实验模型等海量同类文件按目录与文件类型说明，不为数万张同构图片重复写相同描述。
- 明确运行入口、测试入口、训练入口、批量预测入口、数据边界、可再生成目录和不可删除目录。

## 验证标准

1. 后端全套 pytest 通过。
2. 前端 Vitest 全套通过。
3. TypeScript 检查与 Vite 生产构建通过，并重新生成 `build-output/`。
4. `GET /api/status`、本地分类接口和无外部费用的 Agent 假传输测试通过。
5. 搜索确认运行源码不再引用 `prepared/`、`prepared_clean/`、Intro、GSAP 和 `hero-car.jpg`。
6. 当前背景 `showroom-original.jpg` 的 SHA-256 在整理前后保持不变。
7. 删除清单只包含本设计明确列出的绝对项目内目标，删除后记录实际释放空间。

## 风险控制

- 删除前记录目标的绝对路径、文件数和大小，确保路径位于 `E:\课程设计` 内。
- 先完成引用迁移与测试，再逐组删除；任一步失败即停止后续删除。
- 不读取、输出、写入或迁移任何 API Key。
- 不删除用户档案数据库、会话图片、已生成图板、模型和训练指标。
- 当前目录没有 Git 仓库，无法依赖 Git 恢复；因此只删除可再生成缓存、明确重复文件和已被正式数据替代的中间目录。

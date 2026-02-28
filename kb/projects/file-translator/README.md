# File Translator（独立工具项目）

目标：构建一个支持 `docx / md / json / txt` 的文件翻译工具，在保证翻译准确的同时尽量保持原文件格式不变。

## 当前能力（v0.2）
- CLI 翻译入口（`file-translator`）
- Web UI 页面（`file-translator-web`）
- **异步队列任务**（Redis + RQ Worker）
- 文档分块并发翻译（`max_workers`）
- SQLite 术语库（概念中心模型）
- SQLite 翻译缓存（避免重复消耗）
- 翻译引擎：`mock / deepl / google`

## 本地启动（队列版）
```bash
cd kb/projects/file-translator
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 终端1：启动 redis（需本机已安装）
redis-server

# 终端2：启动 worker
file-translator-worker

# 终端3：启动 web
file-translator-web
```
打开：http://127.0.0.1:8088

## Docker Compose 启动
```bash
cd kb/projects/file-translator
docker compose up --build
```

如需真实翻译引擎，设置环境变量：
- `DEEPL_API_KEY`
- `GOOGLE_TRANSLATE_API_KEY`

## 文档结构
- `00-project/`：项目状态与里程碑
- `01-requirements/`：需求文档
- `02-architecture/`：系统架构
- `03-design/`：模块设计与接口
- `04-plan/`：实施计划
- `05-testing/`：测试与验收
- `99-research/`：竞品/开源项目调研

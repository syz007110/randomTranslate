# File Translator（独立工具项目）

## 当前能力（v0.2）
- CLI 翻译入口（`file-translator`）
- Web UI 页面（`file-translator-web`）
- **异步队列任务**（Redis + RQ Worker）
- 文档分块并发翻译（`max_workers`）
- SQLite 术语库（概念中心模型）
- SQLite 翻译缓存（避免重复消耗）
- 翻译引擎：`mock / deepl / google / llm_kimi`

## 本地启动（队列版）
```bash
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
docker compose up --build
```

如需真实翻译引擎，设置环境变量：
- `DEEPL_API_KEY`
- `GOOGLE_TRANSLATE_API_KEY`
- `KIMI_API_KEY`
- `KIMI_BASE_URL`（可选，默认 `https://api.moonshot.cn/v1`）
- `KIMI_MODEL`（可选，默认 `moonshot-v1-8k`）


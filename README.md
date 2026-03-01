# File Translator

支持格式：`docx / md / json / txt`

## v0.2（可用版）
- 前后端可用（Web UI + API + Worker）
- 队列机制：Redis + RQ
- 分块并发翻译（`max_workers`）
- 术语库 + 翻译缓存（SQLite）
- 引擎：`xfyun`（默认）+ `llm_kimi`（手动切换）

## UI 使用说明
- 页面可手动选择引擎（下拉框）
- **默认是 `xfyun`**
- 复杂文本可切 `llm_kimi`

## 推荐启动方式（跨平台，含 Windows）
### Docker Compose（推荐）
1. 复制配置：
```bash
cp .env.example .env
```
Windows PowerShell:
```powershell
copy .env.example .env
```

2. 编辑 `.env`，填入：
- `XFYUN_APP_ID`
- `XFYUN_API_KEY`
- `XFYUN_API_SECRET`
- `KIMI_API_KEY`

3. 启动：
```bash
docker compose up --build
```

4. 访问：
`http://127.0.0.1:8088`

> 这个方式在 Windows 上最省心，不需要你手动安装 Redis。

## 本地启动（不使用 Docker）
### Linux/macOS
```bash
bash scripts/start-local.sh
```

### Windows
```bat
scripts\start-local.bat
```
或
```powershell
.\scripts\start-local.ps1
```

> Windows 本地模式默认只启动 Web。要完整异步队列能力，建议优先用 Docker Compose。

# File Translator

支持格式：`docx / md / json / txt`

## v0.3（可用版）
- 前后端可用（Web UI + API + Worker）
- 默认队列模式（Redis）
- 队列不可用时自动回退同步模式
- 分块并发翻译（`max_workers`）
- 术语库 + 翻译缓存（SQLite）
- 引擎：`xfyun`（默认）+ `llm_kimi`

## UI 使用说明
- 引擎可手动切换
- 默认 `xfyun`
- 复杂文本可切 `llm_kimi`

## 部署策略（你当前环境）
- **Windows**：原生部署（不使用 Docker）+ Redis
- **Ubuntu**：Docker 部署（api + redis + worker）

---

## Ubuntu（Docker）
1. 复制配置：
```bash
cp .env.example .env
```
2. 编辑 `.env`：
- `XFYUN_APP_ID`
- `XFYUN_API_KEY`
- `XFYUN_API_SECRET`
- `KIMI_API_KEY`
3. 启动：
```bash
docker compose up --build -d
```
4. 访问：`http://<ubuntu-ip>:8088`

## Windows（原生 + Redis）
1. 安装并启动 Redis（本机或可访问的 Redis）
2. `.env` 中确保：
```env
REDIS_URL=redis://127.0.0.1:6379/0
```
> 不要写 `redis://redis:6379/0`（那是 Docker 容器内主机名）
3. 在项目根目录执行：
```bat
scripts\start-local.bat
```
4. 访问：`http://127.0.0.1:8088`

> 若 Redis/Worker 暂不可用，UI 会自动回退到同步翻译模式，仍可使用。

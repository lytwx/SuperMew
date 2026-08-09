# 1Panel 部署与外部 PostgreSQL / Redis 对接实施计划

本计划旨在为 SuperMew 项目制定基于 **1Panel** 容器化运维面板的全量部署方案。
根据要求，项目将对接你已有的**外部云服务器 PostgreSQL 和 Redis**，本地 Docker 部署仅保留 FastAPI 后端应用与 Milvus 向量检索相关基础设施（etcd, MinIO, Milvus Standalone, Attu）。

---

## 📋 部署前准备事项（用户需准备）

在开始部署前，请准备好以下信息与环境：

### 1. 外部 PostgreSQL 数据库准备
- [ ] 外部 PostgreSQL 数据库 IP/域名及服务端口（默认 `5432`）
- [ ] 数据库名称（建议创建独立数据库，如 `supermew` 或 `langchain_app`）
- [ ] 数据库用户名及密码
- [ ] **网络安全组/防火墙**：确保部署 1Panel 的服务器 IP 已加入外部 PostgreSQL 所在服务器的白名单，且允许远程 TCP 连接（配置 `pg_hba.conf` 中的 listen_addresses）。

### 2. 外部 Redis 缓存准备
- [ ] 外部 Redis IP/域名及服务端口（默认 `6379`）
- [ ] Redis 认证密码（若无密码留空）
- [ ] **网络安全组/防火墙**：确保 1Panel 服务器 IP 已加入外部 Redis 服务器白名单，允许 6379 端口通信。

### 3. 大模型与应用密钥配置
- [ ] 火山方舟 / OpenAI 兼容 API Key (`ARK_API_KEY`)
- [ ] LLM 模型名称 (`MODEL`, `FAST_MODEL`, `GRADE_MODEL`)
- [ ] JWT 密钥与管理员邀请码 (`JWT_SECRET_KEY`, `ADMIN_INVITE_CODE`)

---

## 🛠️ 拟修改与新增的代码配置

### Component: Backend & Docker Containerization

#### [NEW] [Dockerfile](file:///d:/static/AIProject/SuperMew/Dockerfile)
创建一个多阶段构建（Multi-stage Build）Docker 镜像：
- **Stage 1 (Frontend Build)**：基于 `node:20-alpine` 镜像打包 `frontend` 静态资源到 `frontend/dist`。
- **Stage 2 (Backend Production)**：基于 `python:3.12-slim` 镜像安装 Python 依赖（`uv` / `pip`），并挂载 `frontend/dist` 产物，使用 `uvicorn` 作为生产服务器运行。

#### [MODIFY] [docker-compose.prod.yml](file:///d:/static/AIProject/SuperMew/docker-compose.prod.yml)
- 新增 `backend` 服务节点：镜像自动构建，端口暴露至宿主机 `8000`。
- 移除本地 `postgres` 与 `redis` 容器配置，解耦数据库依赖。
- 挂载 `.env` 环境变量，将 `DATABASE_URL` 与 `REDIS_URL` 指向外部云服务器。
- 保留 Milvus 向量库集群 (`standalone`, `etcd`, `minio`, `attu`)。

#### [MODIFY] [.env.example](file:///d:/static/AIProject/SuperMew/.env.example)
- 增加外部 PostgreSQL (`DATABASE_URL`) 和 Redis (`REDIS_URL`) 的详细配置示例与连接字符串说明。

---

## 🎯 1Panel 界面操作指南（步骤与流程）

### 第一步：上传项目代码与配置 `.env`
1. 将项目代码拉取或上传至 Ubuntu 服务器（例如 `/opt/supermew`）。
2. 根据 `.env.example` 复制创建 `.env` 文件：
   ```bash
   cp .env.example .env
   ```
3. 修改 `.env` 中的外部数据库与缓存地址：
   ```ini
   DATABASE_URL=postgresql+psycopg2://<DB_USER>:<DB_PASSWORD>@<EXTERNAL_PG_IP>:5432/<DB_NAME>
   REDIS_URL=redis://:<REDIS_PASSWORD>@<EXTERNAL_REDIS_IP>:6379/0
   ```

### 第二步：在 1Panel 中导入与拉起编排（Compose）
1. 打开 1Panel 运维面板，点击左侧菜单栏 **【容器】** -> **【编排】** -> **【创建编排】**。
2. 填写编排名称：`supermew`。
3. 选择“本地文件”方式，指向服务器上的 `/opt/supermew/docker-compose.prod.yml`。
4. 点击 **【启动】**，1Panel 会自动拉取镜像、构建后端容器，并拉起 Milvus 向量库与后端服务。

### 第三步：在 1Panel 中配置域名、反向代理与 HTTPS
1. 打开 1Panel 侧边栏 **【网站】** -> **【创建网站】**。
2. 选择 **【反向代理】** 模式：
   - 主域名：填入你的网站域名或服务器公网 IP。
   - 代理地址：`127.0.0.1:8000`（指向 SuperMew FastAPI 后端服务）。
3. **启用 HTTPS**：在网站设置中，点击 **【HTTPS】** -> **【申请证书】**，通过 ACME 一键申请免费 SSL 证书并开启 HTTP 强制跳转 HTTPS。
4. **支持 SSE 打字机输出**：在 Nginx / OpenResty 高级设置中，确保配置了 `proxy_buffering off;`，保证 LangChain 流式响应流畅推送。

---

## 🔍 验证与测试计划

### 1. 自动化与日志验证
- **容器健康检查**：在 1Panel 容器列表检查 `supermew-backend` 与 `supermew-milvus-standalone` 是否处于 `healthy` 或 `running` 状态。
- **数据库表自动初始化**：查看 `supermew-backend` 日志，确认 SQLAlchemy 已成功在外部 PostgreSQL 中创建 `users`、`chat_sessions`、`chat_messages`、`parent_chunks` 等数据表。

### 2. 手动功能验证
- 访问 `https://<your-domain>/docs` 校验 Swagger API 文档接口可用性。
- 访问 `https://<your-domain>/` 进入前端页面，测试管理员登录/注册。
- 上传测试 PDF 文档，验证三级切分与 Milvus 向量入库。
- 发起对话测试，验证流式打字机效果、历史记录落地外部 PG 及父块 Redis 缓存。

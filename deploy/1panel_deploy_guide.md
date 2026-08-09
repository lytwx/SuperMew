# SuperMew 1Panel 应用部署指南

本部署指南用于将 **SuperMew 应用层 (前端 + 后端)** 一键部署到 1Panel 面板中，并直接对接你已部署好的**基础基础设施（Milvus 向量库、PostgreSQL 数据库、Redis 缓存与 Embedding 服务）**。

---

## 📂 部署目录文件结构

所有应用构建与编排文件均位于项目 `deploy/` 目录中：

- `deploy/Dockerfile.frontend`：前端 Vue3 多阶段构建镜像。
- `deploy/nginx.frontend.conf`：前端容器内部 Nginx 配置文件（内置 SSE 打字机反代与接口转发）。
- `deploy/Dockerfile.backend`：后端 FastAPI Python 3.12 容器镜像。
- `deploy/docker-compose.yml`：1Panel Compose 编排文件（管理 `supermew-frontend` 与 `supermew-backend`）。

---

## 🎯 1Panel 部署三步操作

### 第一步：检查并更新 `.env` 配置
确保根目录 [.env](file:///d:/static/AIProject/SuperMew/.env) 中的基础基础设施配置正确：
- **PostgreSQL**：`DATABASE_URL=postgresql+psycopg2://user_Ka4wep:password_tdPaEM@100.120.68.97:5432/user_Ka4wep`
- **Redis**：`REDIS_URL=redis://:redis_pT8YBC@100.120.68.97:6379/0`
- **Milvus**：`MILVUS_HOST=100.110.219.71`，`MILVUS_PORT=19530`
- **Embedding / Rerank**：`EMBEDDING_API_URL=http://100.99.91.88:8001/v1/embeddings`，`RERANK_BINDING_HOST=http://100.99.91.88:8001`

### 第二步：在 1Panel 中拉起 Compose 编排
1. 打开 1Panel 控制台，进入 **【容器】** -> **【编排】** -> **【创建编排】**。
2. 填写名称：`supermew-app`。
3. 选择构建路径，指向项目目录中的 `deploy/docker-compose.yml`。
4. 点击 **【确认】/【启动】**。1Panel 会自动拉起 `supermew-backend` (端口 8000) 与 `supermew-frontend` (端口 8080)。

### 第三步：在 1Panel 中配置域名与 HTTPS 证书
1. 打开 1Panel 菜单 **【网站】** -> **【创建网站】**。
2. 选择类型 **【反向代理】**：
   - 主域名：填入你的访问域名。
   - 代理地址：`127.0.0.1:8080`（指向前端容器端口）。
3. **开启 HTTPS**：点击网站设置 -> **【HTTPS】** -> **【申请证书】**，一键配置 Let's Encrypt 证书并开启 HTTP 强制跳转 HTTPS。

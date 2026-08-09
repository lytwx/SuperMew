#!/usr/bin/env bash
set -e

echo "============================================================"
echo "🚀 构建 SuperMew 前端与后端 Docker 镜像"
echo "============================================================"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "[1/2] 构建后端镜像 (supermew-backend:latest)..."
docker build -f deploy/Dockerfile.backend -t supermew-backend:latest .

echo "[2/2] 构建前端镜像 (supermew-frontend:latest)..."
docker build -f deploy/Dockerfile.frontend -t supermew-frontend:latest .

echo "============================================================"
echo "🎉 镜像构建完成！镜像列表："
echo "  - supermew-backend:latest"
echo "  - supermew-frontend:latest"
echo "============================================================"

@echo off
echo ============================================================
echo [Build] Building SuperMew Backend and Frontend Docker Images
echo ============================================================

cd /d %~dp0..

echo [1/2] Building Backend Image (supermew-backend:latest)...
docker build -f deploy/Dockerfile.backend -t supermew-backend:latest .

echo [2/2] Building Frontend Image (supermew-frontend:latest)...
docker build -f deploy/Dockerfile.frontend -t supermew-frontend:latest .

echo ============================================================
echo [Success] Docker Images Built Successfully!
echo   - supermew-backend:latest
echo   - supermew-frontend:latest
echo ============================================================

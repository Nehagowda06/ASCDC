@echo off
REM ASCDC Deployment Script for Windows
REM This script deploys the ASCDC project using Docker Compose

echo 🚀 Starting ASCDC deployment...

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose is not available. Please install Docker Compose first.
    pause
    exit /b 1
)

REM Create artifacts directory if it doesn't exist
if not exist artifacts mkdir artifacts

REM Build and start services
echo 📦 Building Docker images...
docker-compose build

if %errorlevel% neq 0 (
    echo ❌ Docker build failed
    pause
    exit /b 1
)

echo 🔄 Starting services...
docker-compose up -d

if %errorlevel% neq 0 (
    echo ❌ Failed to start services
    pause
    exit /b 1
)

REM Wait for services to be ready
echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM Check if services are running
echo 🔍 Checking service status...
docker-compose ps

REM Health check
echo 🏥 Performing health check...
curl -f http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Backend is healthy
) else (
    echo ❌ Backend health check failed
    docker-compose logs backend
    pause
    exit /b 1
)

curl -f http://localhost:3000 >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Frontend is healthy
) else (
    echo ❌ Frontend health check failed
    docker-compose logs frontend
    pause
    exit /b 1
)

echo.
echo 🎉 Deployment successful!
echo 📱 Frontend: http://localhost:3000
echo 🔧 Backend API: http://localhost:8000
echo 🌐 Nginx proxy: http://localhost:80
echo.
echo 📋 Useful commands:
echo   View logs: docker-compose logs -f
echo   Stop services: docker-compose down
echo   Restart services: docker-compose restart
echo   Check status: docker-compose ps
echo.
pause

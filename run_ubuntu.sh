#!/bin/bash

# Nexus ASM Backend - Ubuntu Startup Script

echo "🚀 Setting up Nexus ASM Backend on Ubuntu..."

# 1. Update System
sudo apt update

# 2. Install Python 3.11 and venv if missing
sudo apt install -y python3 python3-venv python3-pip

# 3. Create Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# 4. Activate Venv
source venv/bin/activate

# 5. Install Dependencies
echo "⬇️ Installing dependencies..."
pip install -r requirements.txt

# 6. Start Server (Background or Foreground)
echo "✅ Starting Server on Port 8000..."
echo "Press Ctrl+C to stop."

# Run with Gunicorn for production-grade performance (using Uvicorn worker)
pip install gunicorn

# Run gunicorn with 4 workers
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

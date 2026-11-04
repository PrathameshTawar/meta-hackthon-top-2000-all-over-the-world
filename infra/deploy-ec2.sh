#!/usr/bin/env bash
# Saath - 1-Click AWS EC2 Deployment Bootstrap Script
# Tested on Ubuntu 22.04 / 24.04 LTS (x86_64 or arm64)

set -euo pipefail

echo "======================================================="
echo "   SAATH AWS EC2 DEPLOYMENT BOOTSTRAP"
echo "======================================================="

# 1. Update and install prerequisites
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg git

# 2. Install official Docker and Docker Compose plugin (if not installed)
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER"
    echo "Docker installed successfully."
fi

# 3. Clone or pull repository
REPO_URL="https://github.com/PrathameshTawar/meta-hackthon-top-2000-all-over-the-world.git"
APP_DIR="$HOME/saath"

if [ -d "$APP_DIR" ]; then
    echo "Updating existing repository in $APP_DIR..."
    cd "$APP_DIR"
    git pull origin main
else
    echo "Cloning repository into $APP_DIR..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# 4. Configure .env if missing
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env with your real API keys:"
    echo "    nano .env"
    echo ""
fi

# 5. Build and run containers
echo "Starting Saath services with Docker Compose..."
sudo docker compose up -d --build

echo ""
echo "======================================================="
echo "✅ Saath is running!"
echo "   - Web Board (Frontend): http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo 'YOUR_SERVER_IP'):3000"
echo "   - API Backend:          http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo 'YOUR_SERVER_IP'):8000"
echo "   - Health Check:         http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo 'YOUR_SERVER_IP'):8000/healthz"
echo "======================================================="


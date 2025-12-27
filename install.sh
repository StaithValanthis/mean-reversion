#!/bin/bash
set -euo pipefail

# Mean Reversion Trading Bot - Installation Script
# For Ubuntu/Debian systems

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Mean Reversion Trading Bot Installer"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check OS
if [[ ! -f /etc/os-release ]]; then
    echo -e "${RED}Error: Cannot detect OS. This script supports Ubuntu/Debian only.${NC}"
    exit 1
fi

. /etc/os-release
if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
    echo -e "${RED}Error: This script supports Ubuntu/Debian only. Detected: $ID${NC}"
    exit 1
fi

echo -e "${GREEN}Detected OS: $PRETTY_NAME${NC}"
echo ""

# Check if running as root (for systemd, but not required)
IS_ROOT=false
if [[ $EUID -eq 0 ]]; then
    IS_ROOT=true
    echo -e "${YELLOW}Running as root. Systemd service will be installed system-wide.${NC}"
else
    echo "Not running as root. Systemd service will be installed for current user."
fi
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Python3 not found. Installing prerequisites..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip build-essential git curl
else
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 11 ]]; then
        echo -e "${YELLOW}Python 3.11+ required. Found: $PYTHON_VERSION. Installing prerequisites...${NC}"
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip build-essential git curl
    else
        echo -e "${GREEN}Python version OK: $PYTHON_VERSION${NC}"
    fi
fi

# Check other prerequisites
echo "Checking prerequisites..."
MISSING_DEPS=()
for dep in python3-venv python3-pip build-essential git curl; do
    if ! dpkg -l | grep -q "^ii  $dep "; then
        MISSING_DEPS+=("$dep")
    fi
done

if [[ ${#MISSING_DEPS[@]} -gt 0 ]]; then
    echo "Installing missing dependencies: ${MISSING_DEPS[*]}"
    sudo apt-get update
    sudo apt-get install -y "${MISSING_DEPS[@]}"
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [[ -d ".venv" ]]; then
    echo -e "${YELLOW}.venv already exists. Removing old virtual environment...${NC}"
    rm -rf .venv
fi

python3 -m venv .venv
echo -e "${GREEN}Virtual environment created${NC}"
echo ""

# Activate virtual environment and install requirements
echo "Installing Python dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}Dependencies installed${NC}"
echo ""

# Interactive prompts
echo "=========================================="
echo "Configuration"
echo "=========================================="
echo ""

# API Keys
read -p "Enter BYBIT_API_KEY (or press Enter to skip for testnet): " BYBIT_API_KEY
read -sp "Enter BYBIT_API_SECRET (or press Enter to skip for testnet): " BYBIT_API_SECRET
echo ""

# Testnet (default YES)
read -p "Use testnet? [Y/n] (default: Y): " USE_TESTNET
USE_TESTNET=${USE_TESTNET:-Y}
if [[ "$USE_TESTNET" =~ ^[Yy]$ ]]; then
    USE_TESTNET="true"
else
    USE_TESTNET="false"
fi

# Runtime mode (default PAPER)
read -p "Runtime mode? [paper/live] (default: paper): " RUNTIME_MODE
RUNTIME_MODE=${RUNTIME_MODE:-paper}
if [[ "$RUNTIME_MODE" != "paper" && "$RUNTIME_MODE" != "live" ]]; then
    echo -e "${YELLOW}Invalid mode. Defaulting to paper.${NC}"
    RUNTIME_MODE="paper"
fi

# Safety check for live mode
if [[ "$RUNTIME_MODE" == "live" ]]; then
    echo -e "${RED}WARNING: Live mode will place REAL ORDERS with REAL MONEY!${NC}"
    read -p "Type 'I UNDERSTAND' to confirm: " CONFIRM
    if [[ "$CONFIRM" != "I UNDERSTAND" ]]; then
        echo -e "${YELLOW}Live mode not confirmed. Using paper mode.${NC}"
        RUNTIME_MODE="paper"
    fi
fi

# Systemd service (default NO)
read -p "Install systemd service? [y/N] (default: N): " INSTALL_SYSTEMD
INSTALL_SYSTEMD=${INSTALL_SYSTEMD:-N}

# Docker (default NO)
read -p "Install docker/compose dependencies? [y/N] (default: N): " INSTALL_DOCKER
INSTALL_DOCKER=${INSTALL_DOCKER:-N}

echo ""

# Create .env file
echo "Creating .env file..."
if [[ ! -f ".env.example" ]]; then
    echo -e "${YELLOW}Warning: .env.example not found. Creating default .env...${NC}"
    cat > .env.example << 'EOF'
# Bybit API Keys (set these in your actual .env file)
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# Optional: Use testnet (set to true for paper trading on testnet)
BYBIT_TESTNET=true
EOF
fi

# Write .env file
cat > .env << EOF
# Bybit API Keys
BYBIT_API_KEY=${BYBIT_API_KEY:-}
BYBIT_API_SECRET=${BYBIT_API_SECRET:-}

# Use testnet
BYBIT_TESTNET=${USE_TESTNET}
EOF

chmod 600 .env
echo -e "${GREEN}.env file created and secured${NC}"
echo ""

# Update config.yaml
echo "Updating config.yaml..."
if [[ ! -f "config/config.yaml" ]]; then
    echo -e "${RED}Error: config/config.yaml not found!${NC}"
    exit 1
fi

# Use Python to safely update YAML
python3 << PYTHON_EOF
import sys
import re

config_file = "config/config.yaml"
use_testnet = "${USE_TESTNET}"
runtime_mode = "${RUNTIME_MODE}"

try:
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Update testnet setting
    if use_testnet == "true":
        content = re.sub(r'(testnet:\s*)(true|false)', r'\1true', content)
    else:
        content = re.sub(r'(testnet:\s*)(true|false)', r'\1false', content)
    
    # Update runtime mode
    content = re.sub(r'(mode:\s*)(paper|live)', rf'\1{runtime_mode}', content)
    
    with open(config_file, 'w') as f:
        f.write(content)
    
    print("Config file updated successfully")
except Exception as e:
    print(f"Error updating config: {e}")
    sys.exit(1)
PYTHON_EOF

echo -e "${GREEN}Config updated${NC}"
echo ""

# Install Docker (optional)
if [[ "$INSTALL_DOCKER" =~ ^[Yy]$ ]]; then
    echo "Installing Docker and Docker Compose..."
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
    
    echo -e "${GREEN}Docker installed${NC}"
    echo ""
fi

# Install systemd service (optional)
if [[ "$INSTALL_SYSTEMD" =~ ^[Yy]$ ]]; then
    echo "Installing systemd service..."
    
    SERVICE_NAME="bybit-mr-bot"
    WORK_DIR="$SCRIPT_DIR"
    VENV_PYTHON="$WORK_DIR/.venv/bin/python"
    
    # Determine service file location
    if [[ "$IS_ROOT" == "true" ]]; then
        SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    else
        SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
        mkdir -p "$SYSTEMD_USER_DIR"
        SERVICE_FILE="$SYSTEMD_USER_DIR/${SERVICE_NAME}.service"
    fi
    
    # Determine systemctl command
    if [[ "$IS_ROOT" == "true" ]]; then
        SYSTEMCTL_CMD="sudo systemctl"
    else
        SYSTEMCTL_CMD="systemctl --user"
    fi
    
    # Create service file
    if [[ "$IS_ROOT" == "true" ]]; then
        # System-wide service
        cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Bybit Mean Reversion Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
Environment="PATH=$WORK_DIR/.venv/bin:$PATH"
Environment="PYTHONPATH=$WORK_DIR"
EnvironmentFile=$WORK_DIR/.env
ExecStart=/bin/bash -c "cd $WORK_DIR && PYTHONPATH=$WORK_DIR $VENV_PYTHON scripts/live.py --config config/config.yaml --paper"
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    else
        # User-level service (no User= directive)
        cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Bybit Mean Reversion Trading Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$WORK_DIR
Environment="PATH=$WORK_DIR/.venv/bin:$PATH"
Environment="PYTHONPATH=$WORK_DIR"
EnvironmentFile=$WORK_DIR/.env
ExecStart=/bin/bash -c "cd $WORK_DIR && PYTHONPATH=$WORK_DIR $VENV_PYTHON scripts/live.py --config config/config.yaml --paper"
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
    fi

    if [[ "$IS_ROOT" != "true" ]]; then
        # Enable user-level systemd services
        sudo loginctl enable-linger $USER || true
    fi
    
    # Reload systemd and enable service
    if [[ "$IS_ROOT" == "true" ]]; then
        sudo systemctl daemon-reload
        sudo systemctl enable "${SERVICE_NAME}.service"
        echo -e "${GREEN}Systemd service installed and enabled${NC}"
        echo ""
        echo "Service management commands:"
        echo "  Check status: sudo systemctl status ${SERVICE_NAME}"
        echo "  View logs:    sudo journalctl -u ${SERVICE_NAME} -f"
        echo "  Start:        sudo systemctl start ${SERVICE_NAME}"
        echo "  Stop:         sudo systemctl stop ${SERVICE_NAME}"
    else
        $SYSTEMCTL_CMD daemon-reload
        $SYSTEMCTL_CMD enable "${SERVICE_NAME}.service"
        echo -e "${GREEN}User-level systemd service installed and enabled${NC}"
        echo ""
        echo "Service management commands:"
        echo "  Check status: systemctl --user status ${SERVICE_NAME}"
        echo "  View logs:    journalctl --user -u ${SERVICE_NAME} -f"
        echo "  Start:        systemctl --user start ${SERVICE_NAME}"
        echo "  Stop:         systemctl --user stop ${SERVICE_NAME}"
    fi
    echo ""
fi

# Print summary and next steps
echo "=========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Activate virtual environment:"
echo "   ${GREEN}source .venv/bin/activate${NC}"
echo ""
echo "2. Download historical data:"
echo "   ${GREEN}python scripts/download_data.py --config config/config.yaml --days 30 --universe${NC}"
echo ""
echo "3. Run backtest:"
echo "   ${GREEN}python scripts/backtest.py --config config/config.yaml${NC}"
echo ""
echo "4. Run live trading (paper mode):"
echo "   ${GREEN}python scripts/live.py --config config/config.yaml --paper${NC}"
echo ""

if [[ "$INSTALL_SYSTEMD" =~ ^[Yy]$ ]]; then
    echo "5. The systemd service is installed and enabled."
    if [[ "$IS_ROOT" == "true" ]]; then
        echo "   Start it with: ${GREEN}sudo systemctl start ${SERVICE_NAME}${NC}"
    else
        echo "   Start it with: ${GREEN}systemctl --user start ${SERVICE_NAME}${NC}"
    fi
    echo ""
fi

echo "Configuration:"
echo "  Testnet: ${USE_TESTNET}"
echo "  Mode: ${RUNTIME_MODE}"
echo "  API Key: ${BYBIT_API_KEY:+[SET]}${BYBIT_API_KEY:-[NOT SET]}"
echo ""
echo -e "${YELLOW}Note: Your API keys are stored in .env (chmod 600)${NC}"
echo ""


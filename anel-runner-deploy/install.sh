#!/bin/bash
# Install anel-runner on docker-medmus.mutech.zkm.de

set -e

INSTALL_DIR="/opt/anel-runner"
SERVICE_USER="museumstechnik"

echo "=== Installing ANEL Runner ==="

# Create install directory
sudo mkdir -p $INSTALL_DIR
sudo chown $SERVICE_USER:$SERVICE_USER $INSTALL_DIR

# Create virtual environment
python3 -m venv $INSTALL_DIR/venv
source $INSTALL_DIR/venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install fastapi uvicorn pydantic pydantic-settings

# Copy application code
cp -r anel_runner $INSTALL_DIR/

# Create .env file
cat > $INSTALL_DIR/.env << 'EOF'
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=INFO
ANEL_API_KEY=changeme
EOF

# Create systemd service
sudo tee /etc/systemd/system/anel-runner.service > /dev/null << EOF
[Unit]
Description=ANEL Runner - UDP proxy for ANEL power outlets
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m anel_runner.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable anel-runner
sudo systemctl start anel-runner

echo "=== ANEL Runner installed ==="
echo "Check status: sudo systemctl status anel-runner"
echo "View logs: sudo journalctl -u anel-runner -f"

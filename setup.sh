#!/bin/bash

echo "=========================================="
echo "CookieGuard AI - Quick Start"
echo "=========================================="
echo ""

# Check if in correct directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Please run this from the cookieguard-ai directory"
    exit 1
fi

# Step 1: Install Python dependencies
echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages

# Step 2: Train the model
echo ""
echo "[2/3] Training ML model..."
python backend/train_model.py

# Step 3: Instructions
echo ""
echo "[3/3] Setup complete!"
echo ""
echo "=========================================="
echo "To start the application:"
echo "=========================================="
echo ""
echo "Terminal 1 (Backend):"
echo "  cd $(pwd)"
echo "  python backend/app.py"
echo "=========================================="

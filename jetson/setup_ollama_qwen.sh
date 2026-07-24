#!/usr/bin/env bash
#
# Set up Ollama + Qwen2.5-VL-3B on the Jetson Orin Nano (8 GB).
#
# Run it yourself (it needs sudo for the Ollama install):
#     bash ~/setup_ollama_qwen.sh
#
# It is safe to re-run; steps that are already done are skipped.

set -euo pipefail

MODEL="qwen2.5vl:3b"

echo "=========================================================="
echo " Ollama + ${MODEL} setup for Jetson Orin Nano"
echo "=========================================================="

# --- 1. (Recommended) add 8 GB swap so we don't OOM on 8 GB shared RAM ----
if ! swapon --show | grep -q .; then
    echo
    echo ">> No swap found. Creating an 8 GB swapfile (recommended on 8 GB Orin)."
    sudo fallocate -l 8G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    fi
    echo ">> Swap enabled."
else
    echo ">> Swap already present, skipping."
fi

# --- 2. Install Ollama (official arm64 build has CUDA support) -------------
if ! command -v ollama >/dev/null; then
    echo
    echo ">> Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo ">> Ollama already installed: $(ollama --version 2>&1 | head -1)"
fi

# --- 3. Make sure the server is running ------------------------------------
if ! curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
    echo ">> Starting ollama service..."
    sudo systemctl enable --now ollama 2>/dev/null || (nohup ollama serve >/tmp/ollama.log 2>&1 &)
    sleep 3
fi
echo ">> Ollama server: $(curl -sf http://localhost:11434/api/version 2>&1)"

# --- 4. Pull the model -----------------------------------------------------
echo
echo ">> Pulling ${MODEL} (~3 GB, one-time download)..."
ollama pull "${MODEL}"

echo
echo "=========================================================="
echo " Done. Test it with the camera:"
echo "     python3 ask_camera.py 'What do you see?'"
echo " Or chat interactively about the live view:"
echo "     python3 ask_camera.py"
echo "=========================================================="

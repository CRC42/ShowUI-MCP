@echo off
echo === ShowUI-MCP: Creating virtual environment ===
cd /d "D:\git\ShowUI-MCP"

python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create venv
    exit /b 1
)

echo === Installing PyTorch with CUDA 12.8 ===
".venv\Scripts\pip.exe" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 (
    echo ERROR: Failed to install PyTorch
    exit /b 1
)

echo === Installing other dependencies ===
".venv\Scripts\pip.exe" install mcp transformers accelerate qwen-vl-utils Pillow
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

echo === Setup complete! ===
echo Run: scripts\run_showui_mcp.bat

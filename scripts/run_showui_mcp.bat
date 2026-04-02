@echo off
cd /d "D:\git\ShowUI-MCP"
set PYTHONPATH=D:\git\ShowUI-MCP
set PYTHONUTF8=1
"D:\git\ShowUI-MCP\.venv\Scripts\python.exe" -m showui_mcp %*

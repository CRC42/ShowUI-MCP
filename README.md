# ShowUI-MCP

MCP server for GUI element grounding via [ShowUI-2B](https://huggingface.co/showlab/ShowUI-2B) vision model. Locates UI elements in screenshots and returns click coordinates.

## How It Works

```
Screenshot + "同意" ──→ ShowUI-2B (GPU) ──→ [0.93, 0.91] ──→ pixel (2380, 1310)
```

Send a screenshot and a text description of any UI element. The model returns normalized coordinates `[x, y]` (0–1), which are converted to pixel positions.

## Tools

| Tool | Description |
|------|-------------|
| `gui_ground` | Locate a single UI element — returns `{nx, ny, px, py}` |
| `gui_ground_batch` | Locate multiple elements in one screenshot |

## Requirements

- NVIDIA GPU with ≥ 5 GB VRAM (tested on RTX 5080)
- Python 3.10+
- ~4 GB disk for model weights (auto-downloaded from HuggingFace on first run)

## Setup

```bash
git clone <repo-url>
cd ShowUI-MCP
setup_venv.bat          # creates .venv + installs torch, transformers, mcp, etc.
```

## MCP Configuration

Add to your `.mcp.json`:

```json
{
  "showui-mcp": {
    "command": "D:/git/ShowUI-MCP/scripts/run_showui_mcp.bat",
    "args": []
  }
}
```

Restart Claude Code to load the server.

## Usage

```
gui_ground(image_path="C:/screenshot.png", query="同意")
→ {"nx": 0.93, "ny": 0.91, "px": 2380, "py": 1310, "inference_time": 0.7}
```

- First call takes ~15s (model loading), subsequent calls ~0.7s.
- Works with game UIs, desktop apps, web pages — anything in a screenshot.

## License

MIT

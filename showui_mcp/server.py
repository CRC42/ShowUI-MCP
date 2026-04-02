"""
ShowUI-2B MCP Server.

Provides GUI grounding tools via MCP protocol.
Model is loaded once at startup and stays resident on GPU.
"""
import json
import logging
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from showui_mcp.grounding import ShowUIGrounder
from showui_mcp.screenshot import capture_screen, capture_window

logger = logging.getLogger(__name__)

# Global model instance — loaded once, reused across all tool calls
_grounder: ShowUIGrounder | None = None


def _get_grounder() -> ShowUIGrounder:
    global _grounder
    if _grounder is None:
        _grounder = ShowUIGrounder()
        _grounder.load()
    return _grounder


def _resolve_image(arguments: dict) -> dict | str:
    """
    Resolve image source from arguments.
    If window_title is given, capture that window first.
    Returns image_path string, or error dict.
    """
    window_title = arguments.get("window_title")
    image_path = arguments.get("image_path")

    if window_title:
        cap = capture_window(window_title)
        if not cap.get("success"):
            return cap  # error dict
        return cap["path"]
    elif image_path:
        return image_path
    else:
        # Capture full screen as fallback
        return capture_screen()


def create_server() -> Server:
    server = Server("showui-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="gui_ground",
                description=(
                    "Locate a UI element in a screenshot using ShowUI-2B vision model. "
                    "Provide either image_path (existing file) or window_title (auto-captures that window). "
                    "If neither is given, captures the full screen. "
                    "Returns normalized coordinates (0-1) and pixel coordinates."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Description of the UI element to find. "
                                "Can be the element's text label (e.g. '同意', 'Submit'), "
                                "or a description (e.g. 'the search button', '关闭按钮')."
                            ),
                        },
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to a screenshot image (PNG/JPG). Optional if window_title is provided.",
                        },
                        "window_title": {
                            "type": "string",
                            "description": "Window title (partial match) to capture. The window will be brought to foreground and screenshotted automatically.",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="gui_ground_batch",
                description=(
                    "Locate multiple UI elements in one screenshot. "
                    "Provide either image_path or window_title. "
                    "If neither is given, captures the full screen."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of UI element descriptions to locate.",
                        },
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to a screenshot image (PNG/JPG). Optional if window_title is provided.",
                        },
                        "window_title": {
                            "type": "string",
                            "description": "Window title (partial match) to capture.",
                        },
                    },
                    "required": ["queries"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="gui_screenshot",
                description=(
                    "Capture a screenshot of a window or the full screen. "
                    "Returns the saved image path and dimensions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "window_title": {
                            "type": "string",
                            "description": "Window title (partial match) to capture. If omitted, captures the full screen.",
                        },
                        "save_path": {
                            "type": "string",
                            "description": "Path to save the screenshot. If omitted, saves to a temp file.",
                        },
                    },
                    "additionalProperties": False,
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == "gui_screenshot":
                result = _handle_screenshot(arguments)
            elif name == "gui_ground":
                result = _handle_ground(arguments)
            elif name == "gui_ground_batch":
                result = _handle_ground_batch(arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}
        except Exception as e:
            logger.exception("Tool %s failed", name)
            result = {"error": str(e)}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return server


def _handle_screenshot(arguments: dict) -> dict:
    title = arguments.get("window_title")
    save_path = arguments.get("save_path")
    if title:
        result = capture_window(title, save_path)
    else:
        path = capture_screen(save_path)
        result = {"success": True, "path": path}
    return result


def _handle_ground(arguments: dict) -> dict:
    image = _resolve_image(arguments)
    if isinstance(image, dict):
        return image  # error
    grounder = _get_grounder()
    result = grounder.ground(image, arguments["query"])
    result["image_path"] = image
    return result


def _handle_ground_batch(arguments: dict) -> dict:
    image = _resolve_image(arguments)
    if isinstance(image, dict):
        return image  # error
    grounder = _get_grounder()
    results = grounder.ground_batch(image, arguments["queries"])
    return {"image_path": image, "results": results}


async def run_server() -> None:
    """Start the MCP server on stdio."""
    # Pre-load model before accepting connections
    logger.info("Pre-loading ShowUI-2B model...")
    _get_grounder()
    logger.info("Model ready. Starting MCP server on stdio...")

    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

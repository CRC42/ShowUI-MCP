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

logger = logging.getLogger(__name__)

# Global model instance — loaded once, reused across all tool calls
_grounder: ShowUIGrounder | None = None


def _get_grounder() -> ShowUIGrounder:
    global _grounder
    if _grounder is None:
        _grounder = ShowUIGrounder()
        _grounder.load()
    return _grounder


def create_server() -> Server:
    server = Server("showui-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="gui_ground",
                description=(
                    "Locate a UI element in a screenshot using ShowUI-2B vision model. "
                    "Given a screenshot path and a text description of the element, "
                    "returns normalized coordinates (0-1) and pixel coordinates. "
                    "Useful for finding buttons, text fields, links, etc. in game UI, "
                    "desktop apps, or web pages."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to the screenshot image (PNG/JPG).",
                        },
                        "query": {
                            "type": "string",
                            "description": (
                                "Description of the UI element to find. "
                                "Can be the element's text label (e.g. '同意', 'Submit'), "
                                "or a description (e.g. 'the search button', '关闭按钮')."
                            ),
                        },
                    },
                    "required": ["image_path", "query"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="gui_ground_batch",
                description=(
                    "Locate multiple UI elements in a single screenshot. "
                    "More efficient than calling gui_ground repeatedly for the same image."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Absolute path to the screenshot image (PNG/JPG).",
                        },
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of UI element descriptions to locate.",
                        },
                    },
                    "required": ["image_path", "queries"],
                    "additionalProperties": False,
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            grounder = _get_grounder()

            if name == "gui_ground":
                result = grounder.ground(
                    image_path=arguments["image_path"],
                    query=arguments["query"],
                )
            elif name == "gui_ground_batch":
                result = grounder.ground_batch(
                    image_path=arguments["image_path"],
                    queries=arguments["queries"],
                )
            else:
                result = {"error": f"Unknown tool: {name}"}

        except Exception as e:
            logger.exception("Tool %s failed", name)
            result = {"error": str(e)}

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return server


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

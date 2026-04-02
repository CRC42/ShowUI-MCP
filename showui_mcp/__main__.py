"""Entry point for `python -m showui_mcp`."""
import asyncio
import logging
import sys

from showui_mcp.server import run_server


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol; logs go to stderr
    )
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Minimal dropmcp server.

Serve over streamable-HTTP::

    python examples/server.py

The catalog UI is at http://127.0.0.1:8000/ and the MCP endpoint at /mcp.
Override the bind address with DROPMCP_HOST / DROPMCP_PORT.
"""

from pathlib import Path

import dropmcp

_HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    dropmcp.run(
        name="dropmcp example",
        skills=_HERE / "skills",
        prompts=_HERE / "prompts",
    )

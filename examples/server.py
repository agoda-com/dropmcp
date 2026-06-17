"""Minimal dropmcp server.

Run locally over stdio (for Cursor / Claude Desktop)::

    python examples/server.py

Or serve over HTTP::

    DROPMCP_TRANSPORT=http python examples/server.py
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

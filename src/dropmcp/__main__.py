"""``python -m dropmcp`` — serve a dropmcp server configured entirely from
``DROPMCP_*`` environment variables.

Handy for container / env-only deployments where you don't want to write a
``server.py``. There are no command-line options: dropmcp is a hosted
streamable-HTTP server, so everything is driven by the environment.
"""

from __future__ import annotations

import dropmcp

if __name__ == "__main__":
    dropmcp.run()

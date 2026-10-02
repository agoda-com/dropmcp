"""``python -m dropmcp`` — serve a dropmcp server configured entirely from
``DROPMCP_*`` environment variables.

Handy for container / env-only deployments where you don't want to write a
``server.py``. There are no server options on the command line: dropmcp is a
hosted streamable-HTTP server, so everything is driven by the environment.

``python -m dropmcp memory-sql`` prints the reference Postgres DDL for shared
agent memory instead of serving.
"""

from __future__ import annotations

import sys

import dropmcp
from dropmcp.memory.schema_check import memory_sql

if __name__ == "__main__":
    if sys.argv[1:] == ["memory-sql"]:
        sys.stdout.write(memory_sql())
    else:
        dropmcp.run()

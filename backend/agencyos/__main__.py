"""Run AgencyOS:  python -m agencyos [--host 0.0.0.0] [--port 8000]
Seed the demo:  python -m agencyos seed-demo
Import agents:  python -m agencyos import-agents
"""
from __future__ import annotations

import argparse
import logging
import sys


def main() -> None:
    ap = argparse.ArgumentParser(prog="agencyos")
    ap.add_argument("command", nargs="?", default="serve", choices=["serve", "seed-demo", "import-agents"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.command == "serve":
        import uvicorn
        from .api.app import create_app
        uvicorn.run(create_app(), host=a.host, port=a.port, log_level="info")
    elif a.command == "seed-demo":
        from .seed import seed_demo
        print(seed_demo())
    elif a.command == "import-agents":
        from .agents.importer import import_catalogue
        from .agents.registry import seed_builtins
        from .config import load_settings, settings
        from .db import init_db
        load_settings()
        init_db(settings().database_path)
        seed_builtins()
        res = import_catalogue()
        print({k: (v if k != "runnable" else len(v)) for k, v in res.items()})
        sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()

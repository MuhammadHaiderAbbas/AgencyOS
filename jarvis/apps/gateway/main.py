"""Entry point: python -m apps.gateway.main"""
from __future__ import annotations

import argparse

def main():
    parser = argparse.ArgumentParser(description="JARVIS Gateway")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    from packages.config.config import load_settings, settings
    load_settings()
    host = args.host or settings().host
    port = args.port or settings().port

    import uvicorn
    uvicorn.run("apps.gateway.app:create_app", factory=True, host=host, port=port, reload=args.reload)

if __name__ == "__main__":
    main()

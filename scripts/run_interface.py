"""Start the web interface (serves the API and the built interface on one address).

    python scripts/run_interface.py                      # mission database from .env (MISSION_DB_PATH)
    python scripts/run_interface.py --db autre.db        # another mission database
    python scripts/run_interface.py --port 8080

The interface itself is built once with:   cd ui && npm install && npm run build
While working on it:                        cd ui && npm run dev     (http://localhost:5173, API proxied)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from ebios_rm.api.app import create_app  # noqa: E402
from ebios_rm.config import load_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", help="mission database (default: MISSION_DB_PATH)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ui", default="ui", help="interface folder to serve: ui (default) or ui-v2")
    args = parser.parse_args()

    settings = load_settings()
    db_path = args.db or settings.mission_db_path
    ui_dir = ROOT / args.ui / "dist"
    if not ui_dir.is_dir():
        print(f"L'interface n'est pas encore construite : cd {args.ui} && npm install && npm run build")
        print("(l'API fonctionne quand même : http://%s:%d/api/docs)\n" % (args.host, args.port))
    print(f"Base des missions : {db_path}")
    print(f"Interface : http://{args.host}:{args.port}")
    uvicorn.run(create_app(db_path, attack_db_path=settings.attack_db_path, ui_dir=ui_dir),
                host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None

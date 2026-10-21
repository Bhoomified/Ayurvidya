"""Start the API + mobile web app, and print the address to open on your phone.

    python scripts/serve.py              # http://<this laptop's address>:8000
    python scripts/serve.py --port 8080

Phone and laptop must be on the same Wi-Fi. The first time, Windows asks whether Python may use the
network: tick "Private networks" and click Allow. Stop the server with Ctrl+C.
"""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def lan_ip() -> str:
    """This computer's address on the local Wi-Fi (no data is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        sys.exit('Missing packages. Run:  pip install fastapi "uvicorn[standard]"')
    if not (ROOT / "web" / "icon-192.png").exists():
        print("Tip: run  python scripts/make_icons.py  once to create the app icons.")
    ip = lan_ip()
    print("\n  Ayurvidya is starting...")
    print(f"  On this laptop : http://localhost:{args.port}/app/")
    print(f"  On your phone  : http://{ip}:{args.port}/app/   (same Wi-Fi)")
    print("  Stop with Ctrl+C\n")
    import uvicorn
    uvicorn.run("ayurvidya.api:api", host="0.0.0.0", port=args.port, app_dir=str(ROOT / "src"))


if __name__ == "__main__":
    main()
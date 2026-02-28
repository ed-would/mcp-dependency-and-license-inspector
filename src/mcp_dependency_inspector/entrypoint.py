"""Container entrypoint: serve (MCP on port 8000) or smoke (readiness check)."""

import sys
import threading
import time

import httpx

# Import mcp only when needed so stdio usage of server.py is unchanged
def _run_serve() -> None:
    from .server import mcp
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        path="/mcp",
    )


def _wait_for_port(port: int, timeout_seconds: float = 10.0) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        try:
            with httpx.Client(timeout=2.0) as client:
                r = client.get(f"http://127.0.0.1:{port}/health")
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == "ok":
                        return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def run_serve() -> None:
    _run_serve()


def run_smoke() -> None:
    """Quick readiness check: start server in background, GET /health, exit 0 or 1."""
    server_thread = threading.Thread(target=_run_serve, daemon=True)
    server_thread.start()
    if _wait_for_port(8000):
        print("smoke: ok — /health returned 200 and status ok", file=sys.stderr)
        sys.exit(0)
    print(
        "smoke: error — server did not respond on port 8000 /health within timeout. "
        "Check that the image starts correctly and no other process uses port 8000.",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        cmd = "serve"
    else:
        cmd = sys.argv[1].strip().lower()
    if cmd == "serve":
        run_serve()
    elif cmd == "smoke":
        run_smoke()
    else:
        print(
            f"Unknown command: {cmd!r}. Use 'serve' or 'smoke'.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()

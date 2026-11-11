"""Live check, same three calls the professor runs. Usage: python smoke_test.py https://<url> <token>"""
import sys
import urllib.error
import urllib.request


def call(url, token=None):
    req = urllib.request.Request(url, headers={"ngrok-skip-browser-warning": "1"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main(base, token):
    base = base.rstrip("/")
    checks = [
        ("GET /health -> 200", call(f"{base}/health")[0] == 200),
        ("GET /info (no auth) -> 401", call(f"{base}/info")[0] == 401),
        ("GET /info (bad token) -> 401", call(f"{base}/info", "wrong")[0] == 401),
        ("GET /info (token) -> 200", call(f"{base}/info", token)[0] == 200),
    ]
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    sys.exit(0 if all(ok for _, ok in checks) else 1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

"""Optional local server for draft night: serves the board and keeps every save in SQLite.

    uv run python run.py serve            # opens the board in your browser on this computer
    uv run python run.py serve --phone    # also reachable from a phone on the same Wi-Fi

Why: the board already saves in the browser's database, but a browser can lose
that (crash, cleared data). With this server running, every save is also written
to data/drafts.sqlite, including a restore point per save.

By default it only accepts connections from this computer. With --phone it
listens on the local network with no authentication: anyone on the same Wi-Fi
who knows the address can read or change drafts. Standard library only.
"""
import json
import re
import socket
import sqlite3
import time
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .paths import OUTPUT, ROOT

DB_PATH = ROOT / "data" / "drafts.sqlite"
ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")
MAX_BODY = 2_000_000


def connect(path: Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(path or DB_PATH, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, name TEXT, created REAL, updated REAL, picks INTEGER, state TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        n INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, saved REAL, picks INTEGER, state TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS snap_session ON snapshots(session_id, n)")
    return con


@contextmanager
def db():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(OUTPUT), **kw)

    def log_message(self, fmt, *args):  # quieter console: only API writes
        if self.command in ("PUT", "DELETE"):
            super().log_message(fmt, *args)

    # ---- helpers
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sid(self):
        parts = self.path.split("?")[0].strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "sessions"] and ID_RE.match(parts[2]):
            return parts[2]
        return None

    # ---- routes
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", ""):
            self.path = "/board.html"
            return super().do_GET()
        if path == "/api/ping":
            return self._json({"ok": True})
        if path == "/api/sessions":
            with db() as con:
                rows = con.execute("SELECT id, name, created, updated, picks FROM sessions ORDER BY updated DESC").fetchall()
            return self._json([dict(zip(("id", "name", "created", "updated", "picks"), r)) for r in rows])
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] == "snapshots" and ID_RE.match(parts[2]):
            with db() as con:
                rows = con.execute("SELECT n, saved, picks FROM snapshots WHERE session_id=? ORDER BY n DESC LIMIT 300",
                                   (parts[2],)).fetchall()
            return self._json([dict(zip(("n", "saved", "picks"), r)) for r in rows])
        if len(parts) == 3 and parts[:2] == ["api", "snapshots"] and parts[2].isdigit():
            with db() as con:
                r = con.execute("SELECT n, session_id, saved, picks, state FROM snapshots WHERE n=?", (int(parts[2]),)).fetchone()
            if not r:
                return self._json({"error": "not found"}, 404)
            return self._json({"n": r[0], "sessionId": r[1], "saved": r[2], "picks": r[3], "state": json.loads(r[4])})
        if path.startswith("/api/sessions/"):
            sid = self._sid()
            if not sid:
                return self._json({"error": "bad session id"}, 400)
            with db() as con:
                r = con.execute("SELECT id, name, created, updated, picks, state FROM sessions WHERE id=?", (sid,)).fetchone()
            if not r:
                return self._json({"error": "not found"}, 404)
            d = dict(zip(("id", "name", "created", "updated", "picks"), r[:5]))
            d["state"] = json.loads(r[5])
            return self._json(d)
        if path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        return super().do_GET()

    def do_PUT(self):
        sid = self._sid()
        if not sid:
            return self._json({"error": "bad session id"}, 400)
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > MAX_BODY:
            return self._json({"error": "bad body size"}, 413)
        try:
            d = json.loads(self.rfile.read(n))
            state = d["state"]
            picks = len(state.get("picks", []))
            name = str(d.get("name", "Draft"))[:100]
            created = float(d.get("created", time.time() * 1000))
            updated = float(d.get("updated", time.time() * 1000))
        except (ValueError, KeyError, TypeError, AttributeError):
            return self._json({"error": "bad json"}, 400)
        blob = json.dumps(state)
        with db() as con:
            con.execute("""INSERT INTO sessions (id, name, created, updated, picks, state) VALUES (?,?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET name=excluded.name, updated=excluded.updated,
                           picks=excluded.picks, state=excluded.state""", (sid, name, created, updated, picks, blob))
            con.execute("INSERT INTO snapshots (session_id, saved, picks, state) VALUES (?,?,?,?)",
                        (sid, updated, picks, blob))
        return self._json({"ok": True, "saved": updated})

    def do_DELETE(self):
        sid = self._sid()
        if not sid:
            return self._json({"error": "bad session id"}, 400)
        with db() as con:
            con.execute("DELETE FROM sessions WHERE id=?", (sid,))  # snapshots are kept as a safety net
        return self._json({"ok": True})


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def run(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    connect().close()
    srv = ThreadingHTTPServer((host, port), Handler)
    url = f"http://localhost:{port}"
    print(f"Draft board is running at {url}")
    print(f"Every pick is also saved to {DB_PATH}")
    if host == "0.0.0.0":
        print(f"  From a phone on the same Wi-Fi: http://{lan_ip()}:{port}  (no password, stop it after the draft)")
    print("Leave this window open during the draft. Press Ctrl+C to stop.")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Your drafts are in", DB_PATH)

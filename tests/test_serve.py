import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from nhlpool import serve


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(serve, "DB_PATH", tmp_path / "drafts.sqlite")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path / "drafts.sqlite"
    srv.shutdown()


def call(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_save_restore_and_snapshots(server):
    base, db = server
    rec = {"id": "d1", "name": "Draft 1", "created": 1, "updated": 2, "state": {"picks": [{"id": 8478402, "who": "me"}]}}
    call(f"{base}/api/sessions/d1", "PUT", rec)
    rec["updated"], rec["state"]["picks"] = 3, rec["state"]["picks"] + [{"id": 8477492, "who": "other"}]
    call(f"{base}/api/sessions/d1", "PUT", rec)
    assert call(f"{base}/api/sessions") == [{"id": "d1", "name": "Draft 1", "created": 1.0, "updated": 3.0, "picks": 2}]
    got = call(f"{base}/api/sessions/d1")
    assert len(got["state"]["picks"]) == 2
    con = serve.connect(db)
    assert con.execute("SELECT COUNT(*) FROM snapshots WHERE session_id='d1'").fetchone()[0] == 2
    con.close()
    snaps = call(f"{base}/api/sessions/d1/snapshots")
    assert [x["picks"] for x in snaps] == [2, 1]
    first = call(f"{base}/api/snapshots/{snaps[1]['n']}")
    assert len(first["state"]["picks"]) == 1
    call(f"{base}/api/sessions/d1", "DELETE")
    assert call(f"{base}/api/sessions") == []


def test_rejects_bad_ids(server):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as e:
        call(f"{base}/api/sessions/..%2Fetc", "PUT", {"state": {"picks": []}})
    assert e.value.code == 400

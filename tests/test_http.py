"""HTTP-Sitzung: robots.txt und Zwischenspeicher (lokaler Testserver, kein Internet)."""

import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from sportstaettenatlas.http import RobotsVerbot, Sitzung


@pytest.fixture
def server(tmp_path):
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow: /privat/\n")
    (tmp_path / "index.html").write_text("<html><title>Test</title></html>", encoding="utf-8")
    (tmp_path / "privat").mkdir()
    (tmp_path / "privat" / "x.html").write_text("geheim")
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_sitzung_robots_und_cache(server, tmp_path):
    s = Sitzung(tmp_path / "cache", pause_s=0)
    with pytest.raises(RobotsVerbot):
        s.get(server + "/privat/x.html", robots=True)
    a = s.get(server + "/index.html", robots=True)
    assert a.status == 200 and not a.aus_cache
    assert s.get(server + "/index.html", robots=True).aus_cache

"""Exercise runner, subprocess, reports and exit codes against a loopback fixture."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET

import pytest


@pytest.mark.parametrize("unavailable", [False, True], ids=["success", "failure"])
def test_runner_reports_and_exit_code(tmp_path, unavailable):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            status = 503 if unavailable else 401 if self.path.startswith("/api/") else 200
            body = json.dumps({"status": "ok"} if status == 200 else {"detail": "test"}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {**os.environ, "API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
           "E2E_REPORT_DIR": str(tmp_path), "E2E_HTTP_TIMEOUT": "3", "E2E_WAIT_SECONDS": "3",
           "JENKINS_ADMIN_PASSWORD": "must-never-appear-in-reports"}
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / "run.py"),
             "-k", "health or authentication_required"],
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert result.returncode == (1 if unavailable else 0), result.stdout + result.stderr
    manifest = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert manifest["exit_code"] == result.returncode
    suite = ET.parse(tmp_path / "junit.xml").getroot().find("testsuite")
    assert int(suite.attrib["failures"]) == (1 if unavailable else 0)
    assert int(suite.attrib["tests"]) == (1 if unavailable else 4)
    assert len(requests) == (1 if unavailable else 4)
    for filename in ("report.html", "console.log", "requests.log", "resources.json"):
        content = (tmp_path / filename).read_text(encoding="utf-8")
        assert "must-never-appear-in-reports" not in content

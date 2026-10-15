"""Run real HTTP tests; retain console, request log, JUnit, HTML and resource IDs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import threading
from datetime import datetime, timezone
from uuid import uuid4


def main() -> int:
    root = Path(__file__).resolve().parent
    if not os.environ.get("API_BASE_URL"):
        print("Set API_BASE_URL to the deployed control-plane URL (without /api/v1).")
        return 2
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    reports = Path(os.environ.get("E2E_REPORT_DIR", root / "reports" / run_id)).resolve()
    reports.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "E2E_RUN_ID": run_id, "E2E_REPORT_DIR": str(reports),
           "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    env.pop("JENKINS_ADMIN_PASSWORD", None)
    command = [sys.executable, "-m", "pytest", "-c", str(root / "pytest.ini"),
               str(root / "tests"), "--junitxml", str(reports / "junit.xml"),
               "--html", str(reports / "report.html"), "--self-contained-html",
               "--log-file", str(reports / "requests.log"), *sys.argv[1:]]
    print(f"Run: {run_id}\nReports: {reports}", flush=True)
    with (reports / "console.log").open("w", encoding="utf-8") as output:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        interrupted = False
        kill_timer = None

        def interrupt(signum, frame):
            nonlocal interrupted, kill_timer
            if interrupted:
                return
            interrupted = True
            print("Stopping tests; allowing fixture cleanup (up to 180s).", flush=True)
            if os.name != "nt" and process.poll() is None:
                # Keep draining stdout while pytest's finalizers clean up resources.
                process.send_signal(signal.SIGINT)
            kill_timer = threading.Timer(180, process.kill)
            kill_timer.daemon = True
            kill_timer.start()

        previous_handlers = {sig: signal.signal(sig, interrupt)
                             for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            for line in process.stdout:
                output.write(line)
                output.flush()
                print(line, end="", flush=True)
            code = process.wait()
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            if kill_timer:
                kill_timer.cancel()
        if interrupted and code == 0:
            code = 130
    (reports / "run.json").write_text(json.dumps({
        "run_id": run_id, "exit_code": code,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

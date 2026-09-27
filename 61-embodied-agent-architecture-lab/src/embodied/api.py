"""Loopback-only, read-model API for the local architecture workbench."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .cli import ROOT, evaluate, run
from .evidence import canonical
from .ros_campaign import verify_campaign


OUT = ROOT / "reports" / "local"
RUN_RE = re.compile(r"^/api/runs/(mission-\d{3})$")
SCENARIO_RE = re.compile(r"^mission-0(?:[0-5]\d|6[0-3])$")


class WorkbenchHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: object) -> None:
        body = canonical(payload)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/healthz":
            self._send(200, {"status": "ok", "mode": "local-sim-only"})
            return
        if path == "/api/ros-evidence":
            campaign = OUT / "ros-bringup-campaign" / "final.json"
            if not campaign.is_file():
                self._send(
                    200, {"status": "not_available", "evidence_kind": "live_ros_gazebo"}
                )
                return
            try:
                payload = json.loads(campaign.read_text(encoding="utf-8-sig"))
                if not isinstance(payload, dict):
                    raise ValueError("ROS campaign must be a JSON object")
                profile_hash = hashlib.sha256(
                    (ROOT / "configs" / "robotics-profile.lock").read_bytes()
                ).hexdigest()
                summary = verify_campaign(payload, expected_profile_sha256=profile_hash)
            except (OSError, ValueError, TypeError) as error:
                self._send(503, {"status": "invalid", "detail": str(error)})
                return
            self._send(200, summary)
            return
        if path == "/api/overview":
            try:
                summary = json.loads(
                    (OUT / "development-summary.json").read_text(encoding="utf-8")
                )
                profile = json.loads(
                    (ROOT / "configs" / "robotics-profile.lock").read_text(
                        encoding="utf-8"
                    )
                )
                catalog = json.loads(
                    (ROOT / "contracts" / "interface-catalog.v1.json").read_text(
                        encoding="utf-8"
                    )
                )
                runs = sorted(
                    path.stem
                    for path in (OUT / "runs").glob("mission-*.json")
                    if SCENARIO_RE.fullmatch(path.stem)
                )
            except (OSError, ValueError) as error:
                self._send(503, {"error": "evidence unavailable", "detail": str(error)})
                return
            self._send(
                200,
                {
                    "summary": summary,
                    "profile": profile,
                    "catalog": catalog,
                    "runs": runs,
                },
            )
            return
        match = RUN_RE.fullmatch(path)
        if match and SCENARIO_RE.fullmatch(match.group(1)):
            target = OUT / "runs" / f"{match.group(1)}.json"
            try:
                self._send(200, json.loads(target.read_text(encoding="utf-8")))
            except OSError:
                self._send(404, {"error": "run not found"})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/missions":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("request size outside allowed range")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or set(payload) != {"scenario_id"}:
                raise ValueError("only scenario_id is accepted")
            scenario_id = payload["scenario_id"]
            if not isinstance(scenario_id, str) or not SCENARIO_RE.fullmatch(
                scenario_id
            ):
                raise ValueError("only development scenario IDs are available")
            record = run(
                ROOT / "scenarios" / "development" / f"{scenario_id}.json", OUT
            )
        except (ValueError, OSError, RuntimeError) as error:
            self._send(400, {"error": str(error)})
            return
        self._send(200, record)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8161)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost"):
        raise ValueError("local workbench API must bind to loopback")
    if not (OUT / "development-summary.json").exists():
        evaluate("development", OUT, unlock_test=False)
    server = ThreadingHTTPServer((args.host, args.port), WorkbenchHandler)
    print(f"Workbench API listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

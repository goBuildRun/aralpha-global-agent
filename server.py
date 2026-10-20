#!/usr/bin/env python3
"""
AlphaNexus (Aralpha × AlphaRadar) — Hackathon Interactive Demo & API Server.
Zero external dependencies required; runs out-of-the-box on Python 3.10+ (`python3 server.py --port 8766`).
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict

from integrations import (
    EMPIRICAL_SUMMARY,
    GLOBAL_SAFETY_INVARIANTS,
    HALL_OF_FAME_MULTIBAGGERS,
    STRATEGY_OPTIMIZATION_GRID,
    TIMING_WINDOW_MATRIX,
    AlphaNexusHackathonEngine,
)

ENGINE = AlphaNexusHackathonEngine()
STATIC_DIR = Path(__file__).resolve().parent / "static"


def handle_api_request(method: str, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    if method == "GET" and path == "/api/state":
        return {
            "ok": True,
            "empirical_summary": EMPIRICAL_SUMMARY,
            "timing_windows": TIMING_WINDOW_MATRIX,
            "optimization_grid": STRATEGY_OPTIMIZATION_GRID,
            "multibaggers": HALL_OF_FAME_MULTIBAGGERS,
            "safety_invariants": GLOBAL_SAFETY_INVARIANTS,
            "holding_positions": ENGINE.holding_positions,
            "waiting_to_buy_funnel": ENGINE.get_waiting_to_buy_funnel(),
            "contract_audit_logs": ENGINE.contract_audit_logs,
            "macro_evidence_chains": ENGINE.macro_evidence_chains,
            "killswitch_engaged": ENGINE.killswitch_engaged,
            "killswitch_reason": ENGINE.killswitch_reason,
            "telemetry_logs": ENGINE.telemetry_logs,
        }

    if method == "POST" and path == "/api/verify-contract":
        symbol = str(body.get("symbol") or "DNA")
        candidate_contract = str(body.get("candidate_contract") or "0xdeadbeef0000999988887777666655554444fafa")
        chain_name = str(body.get("chain_name") or "BSC")
        record = ENGINE.verify_contract(
            symbol=symbol,
            candidate_contract=candidate_contract,
            chain_name=chain_name,
        )
        return {
            "ok": True,
            "verification": record,
            "contract_audit_logs": ENGINE.contract_audit_logs,
            "telemetry_logs": ENGINE.telemetry_logs,
        }

    if method == "POST" and path == "/api/register-buy":
        symbol = str(body.get("symbol") or "DNA")
        invested_usd = float(body.get("invested_usd") or 300.0)
        custom_price = body.get("entry_price")
        try:
            pos = ENGINE.register_golden_window_buy(
                symbol=symbol,
                invested_usd=invested_usd,
                custom_entry_price=float(custom_price) if custom_price else None,
            )
            return {
                "ok": True,
                "position": pos,
                "holding_positions": ENGINE.holding_positions,
                "waiting_to_buy_funnel": ENGINE.get_waiting_to_buy_funnel(),
                "telemetry_logs": ENGINE.telemetry_logs,
            }
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "telemetry_logs": ENGINE.telemetry_logs,
            }

    if method == "POST" and path == "/api/trigger-25x-alert":
        symbol = str(body.get("symbol") or "COAI")
        res = ENGINE.simulate_25x_principal_recovery_surge(symbol=symbol)
        return {
            "ok": True,
            "alert": res["alert"],
            "updated_position": res["updated_position"],
            "holding_positions": ENGINE.holding_positions,
            "telemetry_logs": ENGINE.telemetry_logs,
        }

    if method == "POST" and path == "/api/macro-scan":
        query = str(body.get("query") or "Synthesize BNB Chain AI Compute, DeSci Genomics (DNA), and Tokenized Stocks (4STOCK) signals.")
        sig = ENGINE.run_alpharadar_macro_scan(query=query)
        return {
            "ok": True,
            "signal": sig,
            "macro_evidence_chains": ENGINE.macro_evidence_chains,
            "telemetry_logs": ENGINE.telemetry_logs,
        }

    if method == "POST" and path == "/api/killswitch":
        engage = body.get("engage")
        reason = str(body.get("reason") or "Operator emergency risk halt test (INV-09)")
        ks = ENGINE.toggle_killswitch(engage=engage if isinstance(engage, bool) else None, reason=reason)
        return {
            "ok": True,
            "killswitch": ks,
            "killswitch_engaged": ENGINE.killswitch_engaged,
            "killswitch_reason": ENGINE.killswitch_reason,
            "telemetry_logs": ENGINE.telemetry_logs,
        }

    return {"ok": False, "error": f"Unknown endpoint {method} {path}"}


class AlphaNexusRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        clean_path = self.path.split("?", 1)[0]
        if clean_path.startswith("/api/"):
            res = handle_api_request("GET", clean_path, {})
            self._send_json(res, 200 if res.get("ok") else 404)
            return

        index_file = STATIC_DIR / "index.html"
        content = index_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802
        clean_path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            body = {}
        res = handle_api_request("POST", clean_path, body)
        self._send_json(res, 200 if res.get("ok") else 400)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="AlphaNexus (Aralpha × AlphaRadar) Hackathon Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8766, help="Bind port (default: 8766)")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), AlphaNexusRequestHandler)
    print(f"🚀 AlphaNexus (Aralpha × AlphaRadar) Workbench running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Tests for the CashTokens read-only sentinel (no network required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bch_cashtokens as bch  # noqa: E402
from server import handle_api_request  # noqa: E402

REG = bch.load_bcmr_registry(json.loads((ROOT / "fixtures" / "bcmr_sample.json").read_text()))
DUSD = "1" * 64
DCT = "2" * 64
FAKE = "f" * 64


def test_bcmr_parsing_uses_latest_snapshot() -> None:
    assert set(REG) == {DUSD, DCT}
    assert REG[DCT]["name"] == "Demo Community Token v2"


def test_verified_token_passes() -> None:
    res = bch.assess_cashtoken({"category": DUSD, "symbol": "DUSD", "name": "Demo Stable Dollar"}, REG)
    assert res["verdict"] == "PASS" and res["automated_action_allowed"] is True


def test_same_ticker_different_category_is_blocked() -> None:
    res = bch.assess_cashtoken({"category": FAKE, "symbol": "DUSD", "name": "whatever"}, REG)
    assert res["verdict"] == "BLOCK"
    assert any(f["rule"] == "R2" for f in res["findings"])


def test_confusable_ticker_is_blocked() -> None:
    res = bch.assess_cashtoken({"category": FAKE, "symbol": "DU5D", "name": ""}, REG)
    assert res["verdict"] == "BLOCK"


def test_unknown_token_fails_closed() -> None:
    res = bch.assess_cashtoken({"category": FAKE, "symbol": "NEWCOIN", "name": "Brand New"}, REG)
    assert res["verdict"] == "FAIL_CLOSED_REVIEW" and res["automated_action_allowed"] is False


def test_bad_category_format_blocked() -> None:
    assert bch.assess_cashtoken({"category": "DUSD", "symbol": "X"}, REG)["verdict"] == "BLOCK"


def test_snapshot_from_real_electrum_shape_minting_and_concentration() -> None:
    # Shape copied from a real Fulcrum `blockchain.address.listunspent ... tokens_only` reply
    # (amount is a string there); owners/amounts here are synthetic.
    utxos = {
        "whale": [{"token_data": {"amount": "950000", "category": DCT}}],
        "issuer": [{"token_data": {"amount": "0", "category": DCT, "nft": {"capability": "minting", "commitment": ""}}}],
        "retail": [{"token_data": {"amount": "50000", "category": DCT}}],
        "other": [{"token_data": {"amount": "999", "category": DUSD}}],
    }
    snap = bch.utxos_to_snapshot(DCT, utxos)
    assert snap["minting_nft_count"] == 1
    assert snap["holdings"]["whale"] == 950000 and "other" not in snap["holdings"]
    res = bch.assess_cashtoken({"category": DCT, "symbol": "DCT", "name": "Demo Community Token v2"}, REG, snap)
    rules = {f["rule"]: f["level"] for f in res["findings"]}
    assert rules == {"R4": "WARN", "R5": "BLOCK"}
    assert res["verdict"] == "BLOCK"


def test_server_endpoint_and_address_guard() -> None:
    r = handle_api_request("POST", "/api/bch/assess", {"candidate": {"category": FAKE, "symbol": "DCT"}})
    assert r["ok"] and r["assessment"]["verdict"] == "BLOCK"
    bad = handle_api_request("POST", "/api/bch/live-token-utxos", {"address": "not-an-address"})
    assert bad["ok"] is False

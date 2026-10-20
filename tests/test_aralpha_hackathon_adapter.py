#!/usr/bin/env python3
"""
Automated verification suite for the AlphaNexus (Aralpha × AlphaRadar) Hackathon Adapter.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations import (
    EMPIRICAL_SUMMARY,
    GLOBAL_SAFETY_INVARIANTS,
    AlphaNexusHackathonEngine,
    build_free_ride_sell_schedule,
    compute_wick_stripped_entry_assessment,
)
from server import handle_api_request


def test_wick_stripped_entry_assessment_excludes_1s_fake_wick() -> None:
    res = compute_wick_stripped_entry_assessment(
        symbol="DNA",
        opening_1s_wick_low=0.0400,
        bars_1h_closes_and_lows=[0.4100, 0.3250, 0.2400, 0.1750, 0.1840],
        live_price=0.1910,
        hours_since_listing=42.0,
    )
    assert res["real_support_low"] == 0.1750
    assert res["buy_zone_high"] == round(0.1750 * 1.22, 6)
    assert res["is_in_buy_price_zone"] is True
    assert res["eligible_status"] == "BUY_WINDOW_ACTIVE"
    assert res["wick_distortion_multiple"] > 4.0


def test_anti_rug_sentinel_blocks_impersonator_contract() -> None:
    engine = AlphaNexusHackathonEngine()
    fake = engine.verify_contract(
        symbol="DNA",
        candidate_contract="0xdeadbeef0000999988887777666655554444fafa",
        chain_name="BSC",
    )
    assert fake["is_authentic_match"] is False
    assert fake["verdict"] == "FAKE_CLONE_SCAM"
    assert "FAIL_CLOSED" in fake["security_metrics"]["execution_gate"]

    official = engine.verify_contract(
        symbol="DNA",
        candidate_contract="0xa991f61940095aea0724ef54077223b048c5cf7b",
        chain_name="BSC",
    )
    assert official["is_authentic_match"] is True
    assert official["verdict"] == "AUTHENTIC_OFFICIAL"


def test_25x_free_ride_schedule_and_alert_trigger() -> None:
    sched = build_free_ride_sell_schedule(
        entry_price=0.2000,
        live_price=0.5200,
        peak_price=0.5500,
        invested_usd=300.0,
    )
    assert sched["principal_recovery_target"] == 0.5000
    assert sched["is_recovery_reached"] is True
    assert sched["sell_40pct_qty"] == 600.0
    assert sched["moonbag_60pct_qty"] == 900.0

    res = handle_api_request("POST", "/api/trigger-25x-alert", {"symbol": "COAI"})
    assert res["ok"] is True
    assert res["alert"]["severity"] == "P1_URGENT_TAKE_PROFIT"
    assert res["updated_position"]["is_recovery_reached"] is True


def test_golden_window_dca_buy_and_killswitch_invariant() -> None:
    state = handle_api_request("GET", "/api/state", {})
    assert state["ok"] is True
    assert len(state["safety_invariants"]) == len(GLOBAL_SAFETY_INVARIANTS) == 9
    assert EMPIRICAL_SUMMARY["total_return_pct"] == 725.82

    buy_res = handle_api_request("POST", "/api/register-buy", {"symbol": "DNA", "invested_usd": 300})
    assert buy_res["ok"] is True
    assert buy_res["position"]["symbol"] == "DNA"

    # Engage KillSwitch (INV-09) and verify new order intents are blocked
    ks_res = handle_api_request("POST", "/api/killswitch", {"engage": True, "reason": "Unit test halt"})
    assert ks_res["ok"] is True
    assert ks_res["killswitch_engaged"] is True

    blocked_buy = handle_api_request("POST", "/api/register-buy", {"symbol": "DRV", "invested_usd": 300})
    assert blocked_buy["ok"] is False
    assert "KillSwitch" in blocked_buy["error"]

    # Release KillSwitch
    handle_api_request("POST", "/api/killswitch", {"engage": False})

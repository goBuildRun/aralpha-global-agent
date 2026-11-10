import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reactive_omni import REACTIVE_NETWORK_CONFIG, simulate_reactive_loop
from server import handle_api_request


def test_reactive_25x_free_ride_loop():
    res = simulate_reactive_loop(
        symbol="COAI",
        entry_support_price=0.1800,
        spot_price=0.4680,  # 2.6x >= 2.5x trigger ($0.4500)
        reserve_liquidity_usd=420000.0,
        min_safe_liquidity_usd=85000.0,
    )
    assert res["system_contract"] == "0x8888888888888888888888888888888888888888"
    assert res["destination_callback_proxy"] == REACTIVE_NETWORK_CONFIG["base_sepolia"]["callback_proxy"]
    assert res["reactive_decision"]["action"] == "FREE_RIDE_25X_PRINCIPAL_RECOVERY"
    assert res["reactive_decision"]["sell_ratio_bps"] == 4000
    assert res["reactive_decision"]["principal_recovered_pct"] == 100.0
    assert res["latency_benchmark"]["total_full_loop_latency_ms"] < 2000


def test_reactive_anti_rug_circuit_breaker():
    res = simulate_reactive_loop(
        symbol="FAKE_MEME",
        entry_support_price=0.1800,
        spot_price=0.2200,
        reserve_liquidity_usd=12000.0,  # Below $85,000 safety floor
        min_safe_liquidity_usd=85000.0,
    )
    assert res["reactive_decision"]["action"] == "EMERGENCY_ANTI_RUG_EXIT"
    assert res["reactive_decision"]["sell_ratio_bps"] == 10000


def test_server_reactive_simulate_endpoint():
    resp = handle_api_request("POST", "/api/reactive/simulate-loop", {"symbol": "COAI", "spot_price": 0.48})
    assert resp["ok"] is True
    assert resp["reactive_loop"]["reactive_decision"]["action"] == "FREE_RIDE_25X_PRINCIPAL_RECOVERY"

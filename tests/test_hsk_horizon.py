#!/usr/bin/env python3
"""
Unit & invariant tests for AlphaNexus × HSK Chain Horizon (`hsk_horizon.py` & `/api/hsk/*`).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hsk_horizon as hsk
from server import handle_api_request


class TestHSKHorizonEngine(unittest.TestCase):
    def test_conversational_intent_bounds_and_profiles(self) -> None:
        intent = hsk.parse_conversational_trading_intent(
            "Run conservative risk $180 on WHSK and USDC every 10 minutes"
        )
        self.assertEqual(intent["risk_appetite"], "conservative")
        self.assertEqual(intent["position_size_usd"], 180.0)
        self.assertEqual(intent["trade_frequency"], "every_10m")
        self.assertIn("WHSK", intent["target_assets"])
        self.assertLessEqual(intent["deterministic_guardrails"]["max_slippage_bps"], 200)

    def test_hskswap_golden_window_and_fail_closed_anti_rug(self) -> None:
        good = hsk.evaluate_hskswap_opportunity(
            symbol="WHSK",
            wick_stripped_support=0.6800,
            hskswap_spot_price=0.7480,
            reference_cex_price=0.7690,
            pool_quote_reserve_usd=185000.0,
            order_size_usd=300.0,
            sell_tax_bps=0,
            top10_holder_bps=4200,
            lp_locked=True,
        )
        self.assertTrue(good["safe_to_execute"])
        self.assertEqual(good["decision"], "EXECUTE_HSKSWAP_GOLDEN_DCA")

        honeypot = hsk.evaluate_hskswap_opportunity(
            symbol="FAKE_HSK",
            sell_tax_bps=9900,
            lp_locked=False,
        )
        self.assertFalse(honeypot["safe_to_execute"])
        self.assertEqual(honeypot["decision"], "BLOCKED_FAIL_CLOSED_ANTI_RUG")

        thin_pool = hsk.evaluate_hskswap_opportunity(
            symbol="WHSK",
            pool_quote_reserve_usd=60000.0,
            order_size_usd=2500.0,
        )
        self.assertFalse(thin_pool["safe_to_execute"])
        self.assertEqual(thin_pool["decision"], "TRANCHE_SLICED_THIN_POOL_GUARD")

    def test_hsp_x402_mandate_enforces_payer_payto_separation(self) -> None:
        ok_mandate = hsk.build_hsp_cart_mandate(
            merchant_name="BuildRun",
            pay_to="0x2d463b4b66c3b066d572471413b8a764b8a2a7d3",
            payer="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            amount_usd="1.00",
            payment_protocol="eip3009",
        )
        method_item = ok_mandate["create_order_params"]["cart_mandate"]["contents"]["payment_request"]["method_data"][0]
        self.assertEqual(method_item["supported_methods"], ["https://www.x402.org/"])
        self.assertEqual(method_item["data"]["x402Version"], 2)

        with self.assertRaises(ValueError):
            hsk.build_hsp_cart_mandate(
                merchant_name="BuildRun",
                pay_to="0x2d463b4b66c3b066d572471413b8a764b8a2a7d3",
                payer="0x2d463b4b66c3b066d572471413b8a764b8a2a7d3",
            )

    def test_server_hsk_api_routes(self) -> None:
        r1 = handle_api_request("POST", "/api/hsk/conversational-intent", {"prompt": "Alpha mode $600 on WHSK/USDT"})
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["intent"]["risk_appetite"], "alpha")

        r2 = handle_api_request(
            "POST",
            "/api/hsk/hsp-mandate",
            {
                "merchant_name": "BuildRun",
                "pay_to": "0x2d463b4b66c3b066d572471413b8a764b8a2a7d3",
                "payer": "0x2d463b4b66c3b066d572471413b8a764b8a2a7d3",
            },
        )
        self.assertFalse(r2["ok"])


if __name__ == "__main__":
    unittest.main()

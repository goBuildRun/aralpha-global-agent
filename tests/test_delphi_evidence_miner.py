import unittest

import delphi_evidence_miner as dem


class TestDelphiEvidenceMiner(unittest.TestCase):
    def test_lmsr_information_gain_positive_on_divergence(self) -> None:
        metrics = dem.compute_lmsr_information_gain(p_market=0.50, p_agent=0.72)
        self.assertEqual(metrics["abs_divergence"], 0.22)
        self.assertGreater(metrics["kl_divergence_bits"], 0.10)
        self.assertGreater(metrics["expected_brier_edge"], 0.04)

    def test_high_signal_primary_source_bundle_approved(self) -> None:
        sample = dem.SAMPLE_DELPHI_MARKETS[0]
        res = dem.evaluate_evidence_bundle(
            market_id=sample["market_id"],
            note=sample["candidate_note"],
            source_links=sample["source_links"],
            supporting_files=sample["supporting_files"],
            p_market=sample["lmsr_implied_prob"],
            p_agent=sample["agent_posterior_prob"],
            submitted_slots_used=1,
        )
        self.assertTrue(res["approved"])
        self.assertEqual(res["decision"], "SUBMIT_TO_DELPHI")
        self.assertEqual(res["slots_remaining_after"], 1)
        self.assertEqual(res["request_headers_preview"]["X-Delphi-Mode"], "competition")
        self.assertEqual(res["request_headers_preview"]["X-Agent-ID"], "AlphaNexus-EvidenceMiner")

    def test_rumor_and_low_divergence_blocked_fail_closed(self) -> None:
        rumor = dem.SAMPLE_DELPHI_MARKETS[3]
        res = dem.evaluate_evidence_bundle(
            market_id=rumor["market_id"],
            note=rumor["candidate_note"],
            source_links=rumor["source_links"],
            supporting_files=[],
            p_market=rumor["lmsr_implied_prob"],
            p_agent=rumor["agent_posterior_prob"],
            submitted_slots_used=0,
        )
        self.assertFalse(res["approved"])
        self.assertEqual(res["decision"], "ABSTAIN_SLOT_CONSERVED")
        joined = " | ".join(res["rejection_reasons"])
        self.assertIn("NO_TIER1_PRIMARY_SOURCE", joined)
        self.assertIn("LOW_INFORMATION_GAIN", joined)

    def test_per_market_3_slot_cap_and_3_file_cap_enforced(self) -> None:
        sample = dem.SAMPLE_DELPHI_MARKETS[1]
        res = dem.evaluate_evidence_bundle(
            market_id=sample["market_id"],
            note=sample["candidate_note"],
            source_links=sample["source_links"],
            supporting_files=["a.json", "b.json", "c.json", "d.json"],
            p_market=0.35,
            p_agent=0.65,
            submitted_slots_used=3,
        )
        self.assertFalse(res["approved"])
        joined = " | ".join(res["rejection_reasons"])
        self.assertIn("QUOTA_EXHAUSTED", joined)
        self.assertIn("SCHEMA_VIOLATION", joined)

    def test_campaign_10_submissions_across_3_markets_eligibility(self) -> None:
        insufficient = [{"market_id": "m1", "judged": True}] * 3 + [{"market_id": "m2", "judged": True}] * 3
        check1 = dem.validate_campaign_eligibility(insufficient)
        self.assertFalse(check1["eligible_for_7250_usdc_pool"])
        self.assertEqual(check1["valid_judged_submissions"], 6)
        self.assertEqual(check1["distinct_markets_covered"], 2)

        qualifying = (
            [{"market_id": "m1", "judged": True}] * 3
            + [{"market_id": "m2", "judged": True}] * 3
            + [{"market_id": "m3", "judged": True}] * 3
            + [{"market_id": "m4", "judged": True}] * 2
        )
        check2 = dem.validate_campaign_eligibility(qualifying)
        self.assertTrue(check2["eligible_for_7250_usdc_pool"])
        self.assertEqual(check2["valid_judged_submissions"], 11)
        self.assertEqual(check2["distinct_markets_covered"], 4)


if __name__ == "__main__":
    unittest.main()

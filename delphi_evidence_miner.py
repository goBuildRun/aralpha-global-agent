#!/usr/bin/env python3
"""
AlphaNexus (Aralpha × AlphaRadar) — Gensyn Delphi Evidence Mining Engine (`delphi_evidence_miner.py`)
=====================================================================================================
Built for DoraHacks `delphi-agent-competition2` ("Agent Arena Competition: Evidence Mining", ID: 2479).

Core Capabilities:
  1. Exact LMSR / Kullback-Leibler Information-Gain Scorer (`compute_lmsr_information_gain`)
     measuring expected forecaster shift between LMSR market implied probability `p_market`
     and AlphaRadar's adversarial dual-pass posterior `p_agent`.
  2. Fail-Closed Evidence Contract & Slot-Conservation Gate (`evaluate_evidence_bundle`):
     - Enforces Delphi's strict `<= 3 submissions per market` and `<= 3 files per submission` caps.
     - Enforces Tier-1 Primary-Source Quorum (rejects secondary blog/social rumor spam).
     - Blocks low-signal noise (`|p_agent - p_market| < 0.08`) so market slots are never wasted.
  3. Competition Qualification Tracker (`validate_campaign_eligibility`):
     - Tracks mandatory minimum (`>= 10` judged submissions across `>= 3` distinct markets).
  4. Official Delphi REST Client & Header Builder (`build_delphi_headers`, `DelphiEvidenceClient`):
     - Reads `DELPHI_API_ACCESS_KEY`, `DELPHI_NETWORK`, and `DELPHI_COMPETITION_PROMPT` from env.
     - Attaches `X-Delphi-Mode: competition` + `X-Agent-ID` / `X-Agent-Harness` / `X-Agent-Model`
       headers so leaderboard attribution maps cleanly to `AlphaNexus-EvidenceMiner`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Sequence


DELPHI_CONFIG: Dict[str, Any] = {
    "competition_slug": "delphi-agent-competition2",
    "dorahacks_hackathon_id": 2479,
    "dorahacks_track_id": 4797,
    "agent_name": "AlphaNexus-EvidenceMiner",
    "harness_id": "aralpha-global-agent/alpharadar-4layer-v1",
    "default_model_tag": "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF+deterministic-lmsr-gate",
    "endpoints": {
        "mainnet": "https://api.delphi.fyi",
        "testnet": "https://delphi-api.gensyn.ai",
        "competition-testnet": "https://delphi-api.gensyn.ai",
    },
    "max_submissions_per_market": 3,
    "max_files_per_submission": 3,
    "min_judged_submissions_total": 10,
    "min_distinct_markets": 3,
    "min_probability_divergence": 0.08,
}

TIER1_PRIMARY_DOMAINS = (
    "federalreserve.gov",
    "sec.gov",
    "bls.gov",
    "treasury.gov",
    "fda.gov",
    "clinicaltrials.gov",
    "europa.eu",
    "github.com",
    "arxiv.org",
    "etherscan.io",
    "basescan.org",
    "bscscan.com",
    "arbiscan.io",
    "gensyn.ai",
    "delphi.fyi",
    "defillama.com",
)

SAMPLE_DELPHI_MARKETS: List[Dict[str, Any]] = [
    {
        "market_id": "delphi-macro-fomc-dec-2026",
        "category": "Economics & Monetary Policy",
        "question": "Will the Federal Reserve hold the target federal funds rate unchanged at the December 2026 FOMC meeting?",
        "resolution_authority": "Federal Reserve Official FOMC Implementation Note (federalreserve.gov)",
        "lmsr_implied_prob": 0.54,
        "agent_posterior_prob": 0.71,
        "submitted_slots_used": 1,
        "candidate_note": (
            "Primary BLS CPI core services print (+0.31% MoM) and Federal Reserve Governor Waller's Nov 2026 "
            "prepared remarks explicitly signal a pause bar unless payrolls contract below +50k. Counter-thesis "
            "(sudden credit spread widening >150 bps) remains untriggered at 104 bps."
        ),
        "source_links": [
            "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            "https://www.bls.gov/cpi/",
        ],
        "supporting_files": ["fomc_statement_diff.json", "bls_core_services_table.csv"],
    },
    {
        "market_id": "delphi-crypto-eth-blob-fee-q4",
        "category": "Crypto & On-Chain Infrastructure",
        "question": "Will Ethereum 7-day rolling L2 blob gas utilization exceed 78% of target capacity before Dec 10, 2026?",
        "resolution_authority": "Ethereum Mainnet Beacon & Execution Block Headers (etherscan.io)",
        "lmsr_implied_prob": 0.39,
        "agent_posterior_prob": 0.63,
        "submitted_slots_used": 0,
        "candidate_note": (
            "On-chain Base + Arbitrum + Unichain batch posting telemetry over the trailing 96 hours shows "
            "mean blob count rising from 4.1 to 5.4 per block following high-frequency DEX settlement upgrades. "
            "Counter-thesis: weekend L2 batch compression could temporarily dip 48h utilization by ~9%."
        ),
        "source_links": [
            "https://etherscan.io/blocks",
            "https://basescan.org/batches",
        ],
        "supporting_files": ["l2_blob_utilization_96h.json"],
    },
    {
        "market_id": "delphi-tech-open-weights-eval-2026",
        "category": "AI & Compute Verification",
        "question": "Will an open-weight model <= 72B parameters surpass 62.0% on SWE-bench Verified official leaderboard by Dec 11, 2026?",
        "resolution_authority": "Official GitHub Benchmark Repository Commit History (github.com)",
        "lmsr_implied_prob": 0.46,
        "agent_posterior_prob": 0.64,
        "submitted_slots_used": 1,
        "candidate_note": (
            "Verified evaluation harness PRs on GitHub and reproducible FP8 checkpoint logs show 59.8% baseline "
            "with +3.1% test-time verification lift under deterministic sandbox budgets."
        ),
        "source_links": [
            "https://github.com/swe-bench/experiments",
            "https://arxiv.org/list/cs.AI/recent",
        ],
        "supporting_files": ["swebench_pr_audit.json"],
    },
    {
        "market_id": "delphi-noise-rumor-example",
        "category": "Crypto Rumor Filter Test",
        "question": "Will unconfirmed social-blog rumor token XYZ list on Tier-1 CEX within 48 hours?",
        "resolution_authority": "Official Exchange Announcement Page",
        "lmsr_implied_prob": 0.32,
        "agent_posterior_prob": 0.35,
        "submitted_slots_used": 0,
        "candidate_note": "Unverified repost from anonymous aggregator blog without primary exchange signature.",
        "source_links": [
            "https://crypto-rumor-blog.example.com/post/xyz-listing-soon",
        ],
        "supporting_files": [],
    },
]


def _clamp_prob(p: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, float(p)))


def compute_lmsr_information_gain(p_market: float, p_agent: float) -> Dict[str, float]:
    """
    Computes Kullback-Leibler divergence D_KL(p_agent || p_market) in bits/nats and
    expected logarithmic scoring improvement when moving an LMSR forecaster from
    `p_market` toward calibrated truth `p_agent`.
    """
    pm = _clamp_prob(p_market)
    pa = _clamp_prob(p_agent)
    abs_diff = abs(pa - pm)
    kl_nats = pa * math.log(pa / pm) + (1.0 - pa) * math.log((1.0 - pa) / (1.0 - pm))
    kl_bits = kl_nats / math.log(2.0)
    brier_edge = (pa - pm) ** 2
    return {
        "p_market": round(pm, 4),
        "p_agent": round(pa, 4),
        "abs_divergence": round(abs_diff, 4),
        "kl_divergence_nats": round(kl_nats, 6),
        "kl_divergence_bits": round(kl_bits, 6),
        "expected_brier_edge": round(brier_edge, 6),
    }


def classify_source_links(links: Sequence[str]) -> Dict[str, Any]:
    primary_hits: List[str] = []
    secondary_or_untrusted: List[str] = []
    malformed: List[str] = []

    for raw in links:
        url = str(raw or "").strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            malformed.append(url)
            continue
        host = parsed.netloc.lower().lstrip("www.")
        if any(host == dom or host.endswith("." + dom) for dom in TIER1_PRIMARY_DOMAINS):
            primary_hits.append(url)
        else:
            secondary_or_untrusted.append(url)

    return {
        "total_links": len(links),
        "primary_count": len(primary_hits),
        "primary_links": primary_hits,
        "secondary_links": secondary_or_untrusted,
        "malformed_links": malformed,
        "has_primary_quorum": len(primary_hits) >= 1 and len(malformed) == 0,
    }


def build_delphi_headers(
    api_key: str | None = None,
    agent_id: str | None = None,
    harness: str | None = None,
    model_name: str | None = None,
    competition_mode: bool = True,
) -> Dict[str, str]:
    """
    Constructs official Delphi REST headers including leaderboard attribution headers
    (`Agent-ID`, `Harness`, `Model`) and `X-Delphi-Mode: competition`.
    """
    resolved_key = api_key if api_key is not None else os.environ.get("DELPHI_API_ACCESS_KEY", "")
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "AlphaNexus-EvidenceMiner/1.0",
        "X-Agent-ID": agent_id or os.environ.get("DELPHI_AGENT_ID") or DELPHI_CONFIG["agent_name"],
        "X-Agent-Harness": harness or os.environ.get("DELPHI_AGENT_HARNESS") or DELPHI_CONFIG["harness_id"],
        "X-Agent-Model": model_name or os.environ.get("DELPHI_AGENT_MODEL") or DELPHI_CONFIG["default_model_tag"],
    }
    if competition_mode:
        headers["X-Delphi-Mode"] = "competition"
    if resolved_key:
        headers["Authorization"] = f"Bearer {resolved_key}"
    return headers


def evaluate_evidence_bundle(
    market_id: str,
    note: str,
    source_links: Sequence[str],
    supporting_files: Sequence[str] | None = None,
    p_market: float = 0.50,
    p_agent: float = 0.68,
    submitted_slots_used: int = 0,
    min_divergence: float | None = None,
) -> Dict[str, Any]:
    """
    Deterministic Fail-Closed Evidence Contract evaluator before consuming a precious
    Delphi per-market submission slot (`max 3 submissions per market`).
    """
    files = list(supporting_files or [])
    threshold = DELPHI_CONFIG["min_probability_divergence"] if min_divergence is None else float(min_divergence)
    info_metrics = compute_lmsr_information_gain(p_market=p_market, p_agent=p_agent)
    source_audit = classify_source_links(source_links)
    clean_note = str(note or "").strip()

    reasons: List[str] = []
    if submitted_slots_used >= DELPHI_CONFIG["max_submissions_per_market"]:
        reasons.append(
            f"QUOTA_EXHAUSTED: {submitted_slots_used}/{DELPHI_CONFIG['max_submissions_per_market']} submissions already used on {market_id}"
        )
    if len(files) > DELPHI_CONFIG["max_files_per_submission"]:
        reasons.append(
            f"SCHEMA_VIOLATION: {len(files)} supporting files exceed Delphi max ({DELPHI_CONFIG['max_files_per_submission']})"
        )
    if len(clean_note) < 40:
        reasons.append("NOTE_TOO_SHORT: analytical rationale must be >= 40 chars with primary citation context")
    if not source_audit["has_primary_quorum"]:
        reasons.append("NO_TIER1_PRIMARY_SOURCE: Fail-Closed rumor filter blocked submission lacking verified primary origin")
    if info_metrics["abs_divergence"] < threshold:
        reasons.append(
            f"LOW_INFORMATION_GAIN: |p_agent - p_market| = {info_metrics['abs_divergence']:.4f} < {threshold:.2f} slot-conservation floor"
        )

    approved = len(reasons) == 0
    digest_seed = json.dumps(
        {
            "market_id": market_id,
            "note": clean_note,
            "links": list(source_links),
            "files": files,
            "p_market": info_metrics["p_market"],
            "p_agent": info_metrics["p_agent"],
        },
        sort_keys=True,
    )
    bundle_sha256 = hashlib.sha256(digest_seed.encode("utf-8")).hexdigest()
    masked_headers = build_delphi_headers(api_key="")
    masked_headers["Authorization"] = (
        "Bearer <DELPHI_API_ACCESS_KEY_SET>" if os.environ.get("DELPHI_API_ACCESS_KEY") else "Bearer <AWAITING_NOV23_KEY>"
    )

    return {
        "market_id": market_id,
        "decision": "SUBMIT_TO_DELPHI" if approved else "ABSTAIN_SLOT_CONSERVED",
        "approved": approved,
        "rejection_reasons": reasons,
        "slots_remaining_after": (
            max(0, DELPHI_CONFIG["max_submissions_per_market"] - submitted_slots_used - (1 if approved else 0))
        ),
        "lmsr_metrics": info_metrics,
        "source_audit": source_audit,
        "delphi_payload": {
            "market_id": market_id,
            "note": clean_note,
            "source_links": list(source_links),
            "supporting_files": files[: DELPHI_CONFIG["max_files_per_submission"]],
            "competition_prompt_hook": os.environ.get(
                "DELPHI_COMPETITION_PROMPT",
                "[Ready for official Nov 23 one-line Delphi competition prompt injection]",
            ),
            "evidence_sha256": bundle_sha256,
        },
        "request_headers_preview": masked_headers,
    }


def validate_campaign_eligibility(judged_submissions: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verifies DoraHacks / Gensyn prize eligibility threshold:
      - At least 10 judged submissions total
      - Across at least 3 distinct markets
      - Respecting <= 3 submissions per individual market
    """
    per_market_counts: Dict[str, int] = {}
    valid_total = 0
    for item in judged_submissions:
        if not item.get("judged", True):
            continue
        m_id = str(item.get("market_id") or "").strip()
        if not m_id:
            continue
        if per_market_counts.get(m_id, 0) < DELPHI_CONFIG["max_submissions_per_market"]:
            per_market_counts[m_id] = per_market_counts.get(m_id, 0) + 1
            valid_total += 1

    distinct_markets = len(per_market_counts)
    meets_total = valid_total >= DELPHI_CONFIG["min_judged_submissions_total"]
    meets_markets = distinct_markets >= DELPHI_CONFIG["min_distinct_markets"]

    return {
        "eligible_for_7250_usdc_pool": meets_total and meets_markets,
        "valid_judged_submissions": valid_total,
        "required_judged_submissions": DELPHI_CONFIG["min_judged_submissions_total"],
        "distinct_markets_covered": distinct_markets,
        "required_distinct_markets": DELPHI_CONFIG["min_distinct_markets"],
        "per_market_counts": per_market_counts,
        "submissions_still_needed": max(0, DELPHI_CONFIG["min_judged_submissions_total"] - valid_total),
        "markets_still_needed": max(0, DELPHI_CONFIG["min_distinct_markets"] - distinct_markets),
    }


class DelphiEvidenceClient:
    """Zero-dependency HTTP client for live Delphi competition API interaction."""

    def __init__(self, network: str | None = None, api_key: str | None = None, base_url: str | None = None) -> None:
        self.network = network or os.environ.get("DELPHI_NETWORK", "competition-testnet")
        self.base_url = (
            base_url
            or os.environ.get("DELPHI_API_BASE_URL")
            or DELPHI_CONFIG["endpoints"].get(self.network, DELPHI_CONFIG["endpoints"]["competition-testnet"])
        ).rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("DELPHI_API_ACCESS_KEY", "")

    def probe_live_api(self, timeout: float = 4.0) -> Dict[str, Any]:
        headers = build_delphi_headers(
            api_key=self.api_key,
            competition_mode=(self.network == "competition-testnet"),
        )
        req = urllib.request.Request(f"{self.base_url}/markets", headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return {"online": True, "status_code": resp.status, "endpoint": self.base_url, "preview": raw[:240]}
        except Exception as exc:
            return {
                "online": False,
                "endpoint": self.base_url,
                "network": self.network,
                "api_key_configured": bool(self.api_key),
                "note": f"Pre-mining standby ({type(exc).__name__}); Delphi API keys unlock Nov 23, 2026 17:00 UTC.",
            }


def main() -> None:
    parser = argparse.ArgumentParser(description="AlphaNexus × Gensyn Delphi Evidence Mining Runner")
    parser.add_argument("--probe", action="store_true", help="Probe live Delphi API endpoint status")
    args = parser.parse_args()

    results = [
        evaluate_evidence_bundle(
            market_id=m["market_id"],
            note=m["candidate_note"],
            source_links=m["source_links"],
            supporting_files=m["supporting_files"],
            p_market=m["lmsr_implied_prob"],
            p_agent=m["agent_posterior_prob"],
            submitted_slots_used=m["submitted_slots_used"],
        )
        for m in SAMPLE_DELPHI_MARKETS
    ]
    out: Dict[str, Any] = {
        "competition": DELPHI_CONFIG,
        "evaluated_bundles": results,
    }
    if args.probe:
        out["live_probe"] = DelphiEvidenceClient().probe_live_api()
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

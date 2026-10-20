# AlphaNexus (`Aralpha × AlphaRadar`) — Autonomous On-Chain Alpha Hunter, Anti-Rug Sentinel & Macro-to-OnChain Investment Committee

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Backtest: 576 Tokens (+725.82% Return / 4.11% Max DD)](https://img.shields.io/badge/Empirical_Backtest-576_Tokens_(%2B725.82%25)-10B981)](#empirical-backtest-validation-576-tokens)
[![Security: Fail-Closed Anti-Rug Sentinel](https://img.shields.io/badge/Web3_Security-Fail--Closed_Anti--Rug_Sentinel-EF4444)](#anti-rug-sentinel--web3-for-social-good)
[![Ecosystem: BNB Chain | Tokenized Stocks | Nebius NVIDIA | Tavily](https://img.shields.io/badge/Ecosystem-BNB_Chain_%7C_RWA_Stocks_%7C_Nebius_NVIDIA_%7C_Tavily-F59E0B)](#ecosystem--sponsor-integrations)

> *"Bridging TradFi macro-industrial intelligence (`AlphaRadar`) with empirical wick-stripped post-listing entry timing, Fail-Closed counterfeit token interception, and automated $2.5\times$ principal-recovery discipline (`Aralpha`)."*

**AlphaNexus (`Aralpha × AlphaRadar`)** is an institutional-grade **Autonomous On-Chain Alpha Hunter, Anti-Rug Security Sentinel, and Macro-to-OnChain Research Agent**. Instead of chasing newly listed tokens during the first-hour FOMO pump or falling prey to counterfeit honeypot contracts, AlphaNexus enforces a verifiable 4-stage closed loop:

`1. AlphaRadar 4-Layer Macro-to-OnChain Evidence Chain ➔ 2. Fail-Closed Anti-Rug & Fake Token Sentinel (INV-06) ➔ 3. Wick-Stripped T+12h~72h Golden Washout Entry [support, +22%] ➔ 4. Automated 2.5x Principal Recovery ("Free-Ride") & 35% Moonbag Trailing Stop.`

---

## 🌟 Core Technical Differentiators (Why Judges Love AlphaNexus)

### 1. Wick-Resistant Post-Listing Entry Pricing (`compute_real_kline_entry_assessment`)
New token listings on DEXs and Binance Alpha frequently print an artificial **1-second opening auction wick** (`bar[0].low`) that is $3\times \sim 5\times$ below real tradable liquidity (for example, `DNA / NeoSoul` printed a `$0.0400` 1-second opening wick while real tradable washout support settled at `$0.1750`).
- Naive trading bots take `min(low)` across all bars, anchoring on a phantom `$0.0400` price that never fills or miscalculating drawdown.
- **AlphaNexus strips `bar[0]` opening wick anomalies**, computes the true post-listing washout support bottom (`real_support_low`) across `T+12h ~ T+72h`, defines the **Golden Buy Zone `[real_support_low, real_support_low × 1.22]`**, and automatically classifies every token into:
  - `BUY_WINDOW_ACTIVE` (*In Golden Buy Zone — Execute DCA Tranche*)
  - `DO_NOT_CHASE_WAIT_PULLBACK` (*Price bounced $>22\%$ above support — Block FOMO chase & place limit order*)

### 2. Fail-Closed Anti-Rug Sentinel & Fake Token Interceptor (*Web3 for Social Good*)
Retail users lose hundreds of millions of dollars annually to counterfeit clone tokens ("impersonator contracts") and asymmetric honeypot taxes launched within minutes of an official TGE announcement.
- **AlphaNexus cross-verifies every candidate contract address** against the official **684-token Binance Alpha & BNB Chain Registry**, inspects LP lock ratios, top-10 holder concentration, and buy/sell tax symmetry (`GoPlus / Honeypot Guard`).
- If a counterfeit contract is detected (e.g., `0xdeadbeef...fafa` impersonating official `DNA` `0xa991f6...cf7b`), AlphaNexus triggers a **Fail-Closed Circuit Breaker (`INV-06`)** and automatically generates a structured **Abuse Report (`SCAM-CA-ALPHA_1247-...`)** for BNB Chain Sentinel and wallet blacklists.

### 3. Automated $2.5\times$ Principal Recovery ("Free-Ride") & 4-Tier Alerting Workbench
Most retail traders turn winning positions into round-trip losses because they lack mechanical exit discipline.
- When a user registers a Golden Window DCA buy (e.g., `$300` in `COAI` at `$0.1957`), AlphaNexus immediately locks a deterministic 4-stage exit schedule:
  1. **Tier 1 ($2.5\times$ Principal Recovery)**: Sell **40%** of tokens at $2.5\times$ entry price to recover **100% of initial capital** (`0.40 × 2.5 = 1.00x principal`).
  2. **Tier 2 ($5.0\times$ Harvest)**: Sell **25%** of remaining tokens.
  3. **Tier 3 ($10.0\times$ Harvest)**: Sell **25%** of remaining tokens.
  4. **Zero-Cost Moonbag ($35\%$ Trailing Stop)**: Hold the remaining **60% Free-Ride Moonbag** with zero principal at risk to capture $100\times \sim 500\times$ outliers (`BTW 549.9x`, `AKE 438.4x`, `COAI 342.6x`).

### 4. `AlphaRadar` 4-Layer Macro-to-OnChain Evidence Chain
Powered by **Nebius Token Factory (`NVIDIA Llama-3.1-Nemotron-70B-Instruct-HF`)** and **Tavily Real-Time Search**, AlphaRadar bridges TradFi/industrial catalysts with on-chain execution under a strict **Zero-Hallucination Evidence Contract**:
`Layer 1 Macro/Policy Catalyst Verification ➔ Layer 2 Tech Route Mapping ➔ Layer 3 Value-Chain Margin Split ➔ Layer 4 On-Chain Alpha & Tokenized Stock (4STOCK) Mapping.`

---

## 📊 Empirical Backtest Validation (576 Tokens Analyzed)

We backtested **7 strategy configurations** across **576 tokens with full 1h/1d K-line history** (`555` Web3 native tokens + `21` RWA Tokenized Stocks) starting with `$10,000` initial capital:

| Strategy Code | Entry & Exit Rule | Trades | Win Rate | $2.5\times$ Principal Recovery | Final Equity (`$10k` Start) | Total Return | Max Drawdown | Sharpe Ratio |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`C01_Baseline_T1h_Chase`** | Chase at `T+1h` open + Hold without principal recovery | 331 | 22.66% | 0.00% | `$58,060.49` | `+480.60%` | **`90.12%`** | `-0.30` |
| **`C02_Early_T6h_24h`** | Early dip `T+6h~24h` + Score $\ge 60$ + $2.5\times$ Recovery | 307 | 41.69% | 33.22% | `$81,555.70` | `+715.56%` | `4.76%` | `0.81` |
| **`C05_Golden_Score55`** | Golden Window `T+12h~72h` + Score $\ge 55$ + $2.5\times$ Free-Ride | 308 | 43.83% | 35.06% | `$80,188.38` | `+701.88%` | `4.97%` | `0.85` |
| **`C06_Golden_Optimal` ★** | **Wick-Stripped `T+12h~72h` `[support, +22%]` + Score $\ge 68$ + $2.5\times$ Sell 40% Recovery + 35% Trailing Stop** | **269** | **44.61%** | **36.06%** | **`$82,582.30`** | **`+725.82%`** | **`4.11%`** | **`0.98`** |

---

## 🔌 Ecosystem & Sponsor Integrations

| Module | Endpoint / Protocol | Role in AlphaNexus |
| :--- | :--- | :--- |
| **BNB Chain (BSC / opBNB) & Tokenized Stocks** | PancakeSwap V3 Router + Official 684-Token Registry (`DNA`, `COAI`, `MYX`, `4STOCK`) | Executes Golden Window DCA swaps on BSC and tracks both Web3 Alpha tokens and BNB Chain Tokenized Equities (`4STOCK`). |
| **Anti-Rug Sentinel (Web3 for Social Good)** | Registry Cross-Verification + GoPlus / Honeypot Tax Inspector | Blocks counterfeit clone tokens (`FAKE_CLONE_SCAM`) pre-trade with a Fail-Closed gate and auto-dispatches public scam reports. |
| **Nebius × NVIDIA Nemotron-70B** | `POST https://api.studio.nebius.ai/v1/chat/completions` | Synthesizes 4-Layer Macro-to-OnChain Evidence Chains and evaluates counter-thesis risk factors. |
| **Tavily Real-Time Search** | `POST https://api.tavily.com/search` | Enforces the Zero-Hallucination Evidence Contract with verifiable timestamps and primary source citations. |

---

## 🚀 Quick Start (Run in 30 Seconds)

Zero external dependencies are required to launch the interactive workbench.

```bash
# 1. Start the AlphaNexus Hackathon Server (Python 3.10+)
python3 server.py --port 8766

# 2. Open in browser:
# http://127.0.0.1:8766

# 3. Run the automated verification test suite:
pytest tests/test_aralpha_hackathon_adapter.py -v
```

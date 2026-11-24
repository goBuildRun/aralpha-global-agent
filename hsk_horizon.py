"""
AlphaNexus (`Aralpha × AlphaRadar`) — HSK Chain Horizon Hackathon Engine (`hsk_horizon.py`)
============================================================================================
Built for HSK Chain Horizon Hackathon · Seoul (`https://dorahacks.io/hackathon/hskchainseoul/detail`):
  1. Track 1 (`AI Agent Trading` on `HSKSwap`):
     - Live JSON-RPC telemetry against HSK Chain Mainnet (`Chain ID: 177`, `https://mainnet.hsk.xyz`)
       and HSK Chain Testnet (`Chain ID: 133`, `https://testnet.hsk.xyz`), verifying live block heights
       and canonical `WHSK` / `USDC` / `USDT` contract bytecode (`eth_getCode`).
     - Conversational Risk & Portfolio Intent Controller (`parse_conversational_trading_intent`):
       translates natural-language trader instructions (position size, trade frequency, risk appetite,
       target HSKSwap pairs) into deterministic bounds without bypassing `INV-06` or `[support, +22%]`.
     - Wick-stripped Golden Entry Window + Cross-Pool Spread & Liquidity-Floor (`<= 1.5%` pool depth)
       execution guard + mechanical `2.5x Free-Ride` (`40%` sell = `100%` principal recovery).
  2. Track 2 (`Agent Payments & A2A Settlement` via `HSP — HashKey Settlement Platform`):
     - Spec-aligned `hsp-agentic-payment` (`https://mcp-qa.hashkeymerchant.com/`) `create_order`
       `cart_mandate` builder (`x402Version: 2`, `supported_methods: ["https://www.x402.org/"]`,
       `eip3009` / `permit2`, `payer != pay_to` separation, zero fabricated tx hashes/signatures).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.request
from typing import Any, Dict, List

HSK_NETWORK_CONFIG: Dict[str, Any] = {
    "mainnet": {
        "name": "HSK Chain Mainnet",
        "chain_id": 177,
        "chain_id_hex": "0xb1",
        "rpc_url": "https://mainnet.hsk.xyz",
        "explorer_url": "https://explorer.hsk.xyz",
    },
    "testnet": {
        "name": "HSK Chain Testnet",
        "chain_id": 133,
        "chain_id_hex": "0x85",
        "rpc_url": "https://testnet.hsk.xyz",
        "faucet_url": "https://faucet.hsk.xyz/",
    },
    "sepolia_usdc_testing": {
        "name": "Ethereum Sepolia (Official Circle Test USDC)",
        "chain_id": 11155111,
        "usdc_contract": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
        "circle_faucet": "https://faucet.circle.com/",
    },
    "canonical_mainnet_tokens": {
        "WHSK": "0xB210D2120d57b758EE163cFfb43e73728c471Cf1",
        "USDC": "0x054ed45810DbBAb8B27668922D110669c9D88D0a",
        "USDT": "0xf1b50ed67a9e2cc94ad3c477779e2d4cbfff9029",
        "WETH": "0xefd4bC9afD210517803f293ABABd701CaeeCdfd0",
        "WBTC": "0x6119ca49a79f5825c8b345f8d7ac36b272565b14",
    },
    "hskswap_app_url": "https://app.hskswap.com/?lng=en-US",
    "hsp_mcp_config": {
        "config_key": "hsp-agentic-payment",
        "transport": "Streamable HTTP",
        "endpoint": "https://mcp-qa.hashkeymerchant.com/",
        "required_tools": [
            "get_chain_config",
            "create_order",
            "get_order",
            "prepare_payment",
            "finalize_payment",
            "estimate_fee",
            "submit_payment",
            "query_payment",
        ],
    },
}

RISK_PROFILE_PRESETS: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "max_position_usd": 250.0,
        "max_slippage_bps": 80,
        "golden_zone_cap_pct": 15.0,
        "min_pool_tvl_usd": 120000.0,
        "free_ride_multiple": 2.5,
        "trailing_stop_pct": 25.0,
    },
    "balanced": {
        "max_position_usd": 500.0,
        "max_slippage_bps": 120,
        "golden_zone_cap_pct": 22.0,
        "min_pool_tvl_usd": 85000.0,
        "free_ride_multiple": 2.5,
        "trailing_stop_pct": 35.0,
    },
    "alpha": {
        "max_position_usd": 1000.0,
        "max_slippage_bps": 180,
        "golden_zone_cap_pct": 22.0,
        "min_pool_tvl_usd": 50000.0,
        "free_ride_multiple": 2.5,
        "trailing_stop_pct": 35.0,
    },
}


def _rpc_call(rpc_url: str, method: str, params: list[Any], timeout: float = 4.0) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    req = urllib.request.Request(
        rpc_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AlphaNexus-HSK-Sentinel/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data.get("result")


def query_hsk_chain_status(timeout: float = 4.0) -> Dict[str, Any]:
    """
    Performs live read-only JSON-RPC verification against HSK Chain Mainnet (`177`)
    and HSK Chain Testnet (`133`), including `eth_getCode` verification of canonical `WHSK` & `USDC`.
    """
    out: Dict[str, Any] = {"networks": {}, "verified_mainnet_tokens": {}}
    for key in ("mainnet", "testnet"):
        cfg = HSK_NETWORK_CONFIG[key]
        try:
            cid_hex = _rpc_call(cfg["rpc_url"], "eth_chainId", [], timeout=timeout)
            blk_hex = _rpc_call(cfg["rpc_url"], "eth_blockNumber", [], timeout=timeout)
            out["networks"][key] = {
                "online": True,
                "chain_id": int(cid_hex, 16) if cid_hex else cfg["chain_id"],
                "block_height": int(blk_hex, 16) if blk_hex else 0,
                "rpc_url": cfg["rpc_url"],
            }
        except Exception as exc:
            out["networks"][key] = {
                "online": False,
                "chain_id": cfg["chain_id"],
                "rpc_url": cfg["rpc_url"],
                "error": type(exc).__name__,
            }

    for sym in ("WHSK", "USDC"):
        addr = HSK_NETWORK_CONFIG["canonical_mainnet_tokens"][sym]
        try:
            code = _rpc_call(HSK_NETWORK_CONFIG["mainnet"]["rpc_url"], "eth_getCode", [addr, "latest"], timeout=timeout)
            has_code = bool(code and code != "0x" and len(code) > 4)
            out["verified_mainnet_tokens"][sym] = {
                "address": addr,
                "bytecode_verified": has_code,
                "bytecode_hex_chars": len(code) - 2 if has_code else 0,
            }
        except Exception:
            out["verified_mainnet_tokens"][sym] = {"address": addr, "bytecode_verified": False}
    return out


def parse_conversational_trading_intent(user_message: str) -> Dict[str, Any]:
    """
    Parses natural-language user instructions into bounded HSKSwap trading parameters
    while preserving hard deterministic safety ceilings (`max_slippage_bps <= 200`, `INV-06` active).
    """
    msg = (user_message or "").strip()
    low = msg.lower()

    if any(k in low for k in ("conservative", "low risk", "safe", "cautious")):
        profile = "conservative"
    elif any(k in low for k in ("aggressive", "high risk", "alpha", "max")):
        profile = "alpha"
    else:
        profile = "balanced"

    preset = dict(RISK_PROFILE_PRESETS[profile])

    usd_match = re.search(r"\$\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:usd|usdc|usdt)", low)
    requested_usd = float(usd_match.group(1) or usd_match.group(2)) if usd_match else preset["max_position_usd"]
    bounded_usd = round(min(max(25.0, requested_usd), 2500.0), 2)

    freq_match = re.search(r"(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours)", low)
    if freq_match:
        val = int(freq_match.group(1))
        unit = "m" if freq_match.group(2).startswith("m") else "h"
        frequency = f"every_{val}{unit}"
    else:
        frequency = "event_driven_15m"

    assets: List[str] = []
    for sym in ("WHSK", "USDC", "USDT", "WETH", "WBTC", "HSK"):
        if sym.lower() in low and sym not in assets:
            assets.append("WHSK" if sym == "HSK" else sym)
    if not assets:
        assets = ["WHSK", "USDC"]

    return {
        "raw_prompt": msg,
        "risk_appetite": profile,
        "position_size_usd": bounded_usd,
        "trade_frequency": frequency,
        "target_assets": assets,
        "deterministic_guardrails": {
            "max_slippage_bps": preset["max_slippage_bps"],
            "golden_zone_upper_pct": preset["golden_zone_cap_pct"],
            "min_pool_tvl_usd": preset["min_pool_tvl_usd"],
            "free_ride_25x_recovery": "Sell 40% at 2.5x -> 100% principal recovered",
            "trailing_moonbag_stop_pct": preset["trailing_stop_pct"],
            "anti_rug_inv06": "FAIL_CLOSED_ENFORCED",
        },
    }


def evaluate_hskswap_opportunity(
    symbol: str = "WHSK",
    candidate_token: str = "0xB210D2120d57b758EE163cFfb43e73728c471Cf1",
    opening_1s_wick_low: float = 0.3100,
    wick_stripped_support: float = 0.6800,
    hskswap_spot_price: float = 0.7480,
    reference_cex_price: float = 0.7690,
    pool_quote_reserve_usd: float = 185000.0,
    order_size_usd: float = 300.0,
    sell_tax_bps: int = 0,
    top10_holder_bps: int = 4200,
    lp_locked: bool = True,
) -> Dict[str, Any]:
    """
    Evaluates an HSKSwap trading opportunity across Anti-Rug (`INV-06`), Wick-Stripped
    Golden Zone `[support, +22%]`, Cross-Venue Spread, and Pool-Depth Slippage (`<= 1.5%` reserve).
    """
    if not lp_locked or sell_tax_bps > 500 or top10_holder_bps >= 8000:
        return {
            "symbol": symbol,
            "token": candidate_token,
            "decision": "BLOCKED_FAIL_CLOSED_ANTI_RUG",
            "safe_to_execute": False,
            "reason": (
                f"INV-06 tripped: lp_locked={lp_locked}, sell_tax_bps={sell_tax_bps} (max 500), "
                f"top10_holder_bps={top10_holder_bps} (max 7999)"
            ),
        }

    max_order_by_depth = round(pool_quote_reserve_usd * 0.015, 2)
    if pool_quote_reserve_usd < 50000.0 or order_size_usd > max_order_by_depth:
        return {
            "symbol": symbol,
            "token": candidate_token,
            "decision": "TRANCHE_SLICED_THIN_POOL_GUARD",
            "safe_to_execute": False,
            "recommended_tranche_usd": min(order_size_usd, max_order_by_depth),
            "reason": (
                f"Order ${order_size_usd:,.2f} exceeds 1.5% pool depth cap (${max_order_by_depth:,.2f}) "
                f"on ${pool_quote_reserve_usd:,.0f} quote reserve"
            ),
        }

    golden_upper = round(wick_stripped_support * 1.22, 6)
    dist_above_support_pct = round(((hskswap_spot_price - wick_stripped_support) / wick_stripped_support) * 100.0, 2)
    spread_bps = round(((reference_cex_price - hskswap_spot_price) / hskswap_spot_price) * 10000.0, 1)

    in_golden_zone = wick_stripped_support <= hskswap_spot_price <= golden_upper
    decision = "EXECUTE_HSKSWAP_GOLDEN_DCA" if in_golden_zone else "DO_NOT_CHASE_PLACE_LIMIT"

    return {
        "symbol": symbol,
        "token": candidate_token,
        "decision": decision,
        "safe_to_execute": in_golden_zone,
        "microstructure": {
            "opening_1s_wick_stripped": opening_1s_wick_low,
            "real_washout_support": wick_stripped_support,
            "golden_zone_band": [wick_stripped_support, golden_upper],
            "hskswap_spot_price": hskswap_spot_price,
            "dist_above_support_pct": dist_above_support_pct,
            "cross_venue_spread_bps": spread_bps,
        },
        "exit_invariants": {
            "free_ride_25x_price": round(hskswap_spot_price * 2.5, 6),
            "free_ride_sell_ratio_bps": 4000,
            "moonbag_trailing_stop_bps": 3500,
            "max_order_depth_cap_usd": max_order_by_depth,
        },
        "reason": (
            f"Spot ${hskswap_spot_price:.4f} is +{dist_above_support_pct}% above wick-stripped support "
            f"${wick_stripped_support:.4f} with +{spread_bps} bps cross-venue spread"
        ),
    }


def build_hsp_cart_mandate(
    merchant_name: str,
    pay_to: str,
    payer: str,
    amount_usd: str = "1.00",
    chain_id: int = 11155111,
    network: str = "ethereum-sepolia",
    token_address: str = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
    token_symbol: str = "USDC",
    token_decimals: int = 6,
    payment_protocol: str = "eip3009",
) -> Dict[str, Any]:
    """
    Constructs an official HSP Agentic Payment (`hsp-agentic-payment`) `create_order` request
    strictly following the HSK Chain Horizon `Agentic Payment — Setup and Execution Guide`:
      - Enforces `payer != pay_to` and valid 42-char EVM addresses.
      - Uses `supported_methods: ["https://www.x402.org/"]` and `data.x402Version: 2`.
      - Never fabricates wallet signatures, `tx_signature`, or `payment-finalized` states.
    """
    addr_re = re.compile(r"^0x[0-9a-fA-F]{40}$")
    clean_merchant = (merchant_name or "").strip()
    clean_pay_to = (pay_to or "").strip()
    clean_payer = (payer or "").strip()

    if not clean_merchant:
        raise ValueError("merchant_name is required for hackathon team attribution")
    if not addr_re.match(clean_pay_to) or not addr_re.match(clean_payer):
        raise ValueError("pay_to and payer must be 42-character 0x EVM addresses")
    if clean_pay_to.lower() == clean_payer.lower():
        raise ValueError("HSP safety rule: payer address must not equal pay_to recipient address")
    if payment_protocol not in ("eip3009", "permit2"):
        raise ValueError("payment_protocol must be 'eip3009' or 'permit2'")

    now_utc = dt.datetime.now(dt.timezone.utc)
    expiry_rfc3339 = (now_utc + dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    seed = f"{clean_merchant}|{clean_pay_to.lower()}|{clean_payer.lower()}|{amount_usd}|{expiry_rfc3339}"
    cart_id = "cart-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    cart_mandate = {
        "contents": {
            "id": cart_id,
            "cart_expiry": expiry_rfc3339,
            "payment_request": {
                "method_data": [
                    {
                        "supported_methods": ["https://www.x402.org/"],
                        "data": {
                            "x402Version": 2,
                            "network": network,
                            "chain_id": chain_id,
                            "coin": token_symbol,
                            "contract_address": token_address,
                            "decimals": token_decimals,
                            "payment_protocol": payment_protocol,
                        },
                    }
                ],
                "details": {
                    "total": {
                        "label": f"{clean_merchant} AlphaNexus Verified Signal Mandate",
                        "amount": {"currency": "USD", "value": str(amount_usd)},
                    }
                },
            },
        }
    }

    cart_hash = "0x" + hashlib.sha256(json.dumps(cart_mandate, sort_keys=True).encode("utf-8")).hexdigest()
    primary_type = "TransferWithAuthorization" if payment_protocol == "eip3009" else "PermitTransferFrom"

    return {
        "mcp_server": HSK_NETWORK_CONFIG["hsp_mcp_config"]["config_key"],
        "mcp_endpoint": HSK_NETWORK_CONFIG["hsp_mcp_config"]["endpoint"],
        "payer_confirmed": clean_payer,
        "create_order_params": {
            "merchant_name": clean_merchant,
            "pay_to": clean_pay_to,
            "cart_mandate": cart_mandate,
        },
        "expected_signing_flow": {
            "step_1": "prepare_payment(flow_id, payer, protocol)",
            "step_2": f"Human approval #1 -> Wallet EIP-712 sign ({primaryType}) over exact token_total_raw"
            if (primaryType := primary_type)
            else "",
            "step_3": "finalize_payment(signature, payment_payload, payment_mandate_contents, cart_hash)",
            "step_4": "Human approval #2 -> submit_payment(payment_mandate_json) -> poll query_payment every 15s until payment-finalized",
        },
        "local_commitment_digest": cart_hash,
        "execution_status": "AWAITING_HSP_QA_IP_ALLOWLIST_AND_USER_APPROVAL",
    }

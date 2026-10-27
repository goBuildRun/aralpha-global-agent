#!/usr/bin/env python3
"""
AlphaNexus — Bitcoin Cash CashTokens read-only anti-counterfeit sentinel.

Zero third-party dependencies (Python 3.10+ stdlib only). Read-only: never signs or
broadcasts transactions and never touches private keys.

What this module really does:
1. `ElectrumCashClient` — minimal Electrum Cash protocol (Fulcrum) JSON-RPC client over TLS.
   Used to read the chain tip and token-bearing UTXOs (`token_data`) for given addresses.
2. `load_bcmr_registry` — parses a Bitcoin Cash Metadata Registry (BCMR) JSON document
   into a verified `category -> {symbol, name, decimals}` map. You choose which registry to trust.
3. `assess_cashtoken` — deterministic rule engine (zero LLM involvement):
     R1  category id must be 32-byte hex (CashTokens identity is the category, never the ticker)
     R2  ticker/name impersonation: same normalized symbol/name as a verified token but a
         different category  -> BLOCK
     R3  category not in the trusted registry -> FAIL_CLOSED_REVIEW (no automated action)
     R4  a live minting-capability NFT for the category exists -> supply can still be inflated
     R5  top-10 holder concentration over threshold (needs a holder snapshot you supply)
"""

from __future__ import annotations

import json
import re
import socket
import ssl
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. Electrum Cash (Fulcrum) client
# ---------------------------------------------------------------------------

DEFAULT_FULCRUM_SERVERS: List[Tuple[str, int]] = [
    ("bch.imaginary.cash", 50002),
    ("electroncash.de", 50002),
    ("bch.loping.net", 50002),
]


class ElectrumCashClient:
    def __init__(self, host: str, port: int = 50002, timeout: float = 10.0, use_tls: bool = True) -> None:
        self.host, self.port, self.timeout, self.use_tls = host, port, timeout, use_tls
        self._sock: Optional[socket.socket] = None
        self._buf = b""
        self._next_id = 0

    def __enter__(self) -> "ElectrumCashClient":
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        if self.use_tls:
            ctx = ssl.create_default_context()
            # Many community Fulcrum servers use self-signed certs; we only read public data.
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            raw = ctx.wrap_socket(raw, server_hostname=self.host)
        self._sock = raw
        self.call("server.version", ["AlphaNexus-sentinel", "1.5"])
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def call(self, method: str, params: Optional[list] = None) -> Any:
        assert self._sock is not None, "use within a `with` block"
        self._next_id += 1
        req_id = self._next_id
        self._sock.sendall((json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or []}) + "\n").encode())
        while True:
            while b"\n" not in self._buf:
                chunk = self._sock.recv(65536)
                if not chunk:
                    raise ConnectionError("server closed connection")
                self._buf += chunk
            line, self._buf = self._buf.split(b"\n", 1)
            msg = json.loads(line)
            if msg.get("id") != req_id:
                continue  # skip notifications
            if msg.get("error"):
                raise RuntimeError(f"{method} failed: {msg['error']}")
            return msg.get("result")

    def chain_tip(self) -> Dict[str, Any]:
        return self.call("blockchain.headers.subscribe")

    def token_utxos(self, address: str) -> List[Dict[str, Any]]:
        """UTXOs carrying CashTokens for a cashaddr (`token_filter=tokens_only`, protocol >= 1.5)."""
        return self.call("blockchain.address.listunspent", [address, "tokens_only"]) or []


def utxos_to_snapshot(category: str, utxos_by_owner: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Aggregate Electrum `token_data` UTXOs into the snapshot shape `assess_cashtoken` expects."""
    holdings: Dict[str, int] = {}
    minting_nfts = 0
    for owner, utxos in utxos_by_owner.items():
        for u in utxos:
            td = u.get("token_data") or {}
            if td.get("category") != category:
                continue
            holdings[owner] = holdings.get(owner, 0) + int(td.get("amount") or 0)
            if (td.get("nft") or {}).get("capability") == "minting":
                minting_nfts += 1
    return {"category": category, "holdings": holdings, "minting_nft_count": minting_nfts}


# ---------------------------------------------------------------------------
# 2. BCMR registry parsing
# ---------------------------------------------------------------------------

CATEGORY_RE = re.compile(r"^[0-9a-f]{64}$")


def load_bcmr_registry(doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return {category: {symbol, name, decimals}} using the latest snapshot of each identity."""
    out: Dict[str, Dict[str, Any]] = {}
    for _authbase, history in (doc.get("identities") or {}).items():
        if not isinstance(history, dict) or not history:
            continue
        latest = history[max(history.keys())]  # ISO timestamps sort lexicographically
        token = latest.get("token") or {}
        cat = str(token.get("category") or "").lower()
        if CATEGORY_RE.match(cat):
            out[cat] = {"symbol": token.get("symbol", ""), "name": latest.get("name", ""), "decimals": token.get("decimals", 0)}
    return out


# ---------------------------------------------------------------------------
# 3. Deterministic assessment
# ---------------------------------------------------------------------------

_CONFUSABLES = str.maketrans({"0": "o", "1": "l", "i": "l", "5": "s", "$": "s", "3": "e", "4": "a", "7": "t"})


def normalize_label(s: str) -> str:
    s = re.sub(r"[^0-9a-z$]", "", (s or "").lower())
    return s.translate(_CONFUSABLES)


def top_n_share(holdings: Dict[str, int], n: int = 10) -> Optional[float]:
    total = sum(v for v in holdings.values() if v > 0)
    if total <= 0:
        return None
    top = sorted((v for v in holdings.values() if v > 0), reverse=True)[:n]
    return sum(top) / total


def assess_cashtoken(
    candidate: Dict[str, Any],
    registry: Dict[str, Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]] = None,
    top10_warn: float = 0.60,
    top10_block: float = 0.90,
) -> Dict[str, Any]:
    """
    candidate: {"category": hex, "symbol": str, "name": str}  (what a UI/DEX listing claims)
    registry : output of load_bcmr_registry (the registry YOU trust)
    snapshot : optional output of utxos_to_snapshot / your indexer
    """
    findings: List[Dict[str, str]] = []
    cat = str(candidate.get("category") or "").lower()
    sym_n, name_n = normalize_label(candidate.get("symbol", "")), normalize_label(candidate.get("name", ""))

    if not CATEGORY_RE.match(cat):
        findings.append({"rule": "R1", "level": "BLOCK", "detail": "category is not a 32-byte hex id"})

    for vcat, meta in registry.items():
        if vcat == cat:
            continue
        if (sym_n and sym_n == normalize_label(meta.get("symbol", ""))) or (name_n and name_n == normalize_label(meta.get("name", ""))):
            findings.append({"rule": "R2", "level": "BLOCK", "detail": f"impersonates verified {meta.get('symbol')} ({vcat[:12]}...)"})
            break

    verified = cat in registry
    if not verified:
        findings.append({"rule": "R3", "level": "REVIEW", "detail": "category not in trusted BCMR registry"})

    if snapshot:
        if int(snapshot.get("minting_nft_count") or 0) > 0:
            findings.append({"rule": "R4", "level": "WARN", "detail": "minting-capability NFT still exists; supply can be inflated"})
        share = top_n_share(snapshot.get("holdings") or {})
        if share is not None:
            if share >= top10_block:
                findings.append({"rule": "R5", "level": "BLOCK", "detail": f"top-10 holders control {share:.0%}"})
            elif share >= top10_warn:
                findings.append({"rule": "R5", "level": "WARN", "detail": f"top-10 holders control {share:.0%}"})

    levels = {f["level"] for f in findings}
    verdict = "BLOCK" if "BLOCK" in levels else "FAIL_CLOSED_REVIEW" if "REVIEW" in levels else "WARN" if "WARN" in levels else "PASS"
    return {
        "category": cat,
        "claimed_symbol": candidate.get("symbol", ""),
        "verified_in_registry": verified,
        "verdict": verdict,
        "automated_action_allowed": verdict in ("PASS", "WARN"),
        "findings": findings,
    }


def assess_many(candidates: Iterable[Dict[str, Any]], registry: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [assess_cashtoken(c, registry) for c in candidates]

#!/usr/bin/env python3
"""
gitlawb × Nansen: Smart Developer Intelligence
===============================================
Proof of Concept — Nansen CLI Hackathon Week 1 (Mar 22, 2026)

Instead of asking "is this developer smart money?"
we flip it: "which smart money wallets are building in crypto?"

Flow:
  1. Pull live Smart Money DEX traders from Nansen
  2. Profile each trader: balance, transactions, PnL
  3. Cross-reference their holdings against Smart Money top picks
  4. Generate a real gitlawb DID (Ed25519) for each wallet
  5. Output a ranked Smart Developer Leaderboard

Every gitlawb identity is a cryptographic DID. In production,
developers link their DID to a wallet address. This PoC shows
what that leaderboard looks like once they do.

Usage:
    export NANSEN_API_KEY=<key>
    python3 smart_dev_score.py
"""

import subprocess, json, os, sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

CHAIN   = "ethereum"
GL_BIN  = "/Users/kevin/Projects/gitlawb/target/release/gl"
N_DEVS  = 5   # how many smart money wallets to profile

# Fictional gitlawb repos assigned to each smart money wallet for the demo
REPOS = [
    "defi-core/yield-optimizer",
    "dao-tooling/governance-sdk",
    "layer2/bridge-protocol",
    "nft-infra/provenance-engine",
    "chain-analytics/onchain-indexer",
]

# ── Nansen CLI ────────────────────────────────────────────────────────────────

api_calls = []

def nansen(subcmd: str) -> dict | None:
    cmd = f"nansen {subcmd}"
    api_calls.append(cmd)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        parsed = json.loads(r.stdout)
        if not parsed.get("success"):
            code = parsed.get("code", "")
            if code == "CREDITS_EXHAUSTED":
                print(f"\n  ERROR: credits exhausted after {len(api_calls)} calls\n")
                sys.exit(1)
            elif code == "FORBIDDEN":
                return None  # skip gracefully
        return parsed
    except json.JSONDecodeError:
        return None

def gl(subcmd: str) -> str:
    r = subprocess.run(f"{GL_BIN} {subcmd}", shell=True, capture_output=True, text=True)
    return r.stdout.strip()

def f(val) -> float:
    try: return float(val or 0)
    except: return 0.0

# ── Step 1: Pull smart money context + trader addresses ───────────────────────

def get_smart_money_tokens() -> set[str]:
    """Get token symbols smart money is currently holding."""
    data = nansen(f"research smart-money holdings --chain {CHAIN} --limit 20 --fields token_symbol,value_usd,holders_count")
    if not data or not data.get("success"):
        return set()
    rows = data.get("data", {}).get("data", data.get("data", []))
    if isinstance(rows, dict): rows = rows.get("data", [])
    return {r.get("token_symbol", "") for r in rows if r.get("token_symbol")}

def get_smart_money_netflow() -> list[dict]:
    """Get top net inflow tokens — what smart money is buying."""
    data = nansen(f"research smart-money netflow --chain {CHAIN} --limit 10 --fields token_symbol,net_flow_7d_usd,trader_count")
    if not data or not data.get("success"):
        return []
    rows = data.get("data", {}).get("data", data.get("data", []))
    if isinstance(rows, dict): rows = rows.get("data", [])
    return sorted(rows, key=lambda r: f(r.get("net_flow_7d_usd")), reverse=True)[:5]

def get_trader_addresses() -> list[dict]:
    """Get unique smart money trader addresses from DEX trades across chains."""
    seen, traders = set(), []

    for chain in [CHAIN, "base", "solana", "bnb"]:
        if len(traders) >= N_DEVS:
            break
        data = nansen(f"research smart-money dex-trades --chain {chain} --limit 100 --fields trader_address,trader_address_label,trade_value_usd,token_bought_symbol")
        if not data or not data.get("success"):
            continue
        rows = data.get("data", {}).get("data", data.get("data", []))
        if isinstance(rows, dict): rows = rows.get("data", [])
        for r in rows:
            addr = r.get("trader_address", "")
            if addr and addr not in seen:
                seen.add(addr)
                traders.append({
                    "address": addr,
                    "label":   r.get("trader_address_label", addr[:10] + "..."),
                    "bought":  r.get("token_bought_symbol", "?"),
                    "chain":   chain,
                })
            if len(traders) >= N_DEVS:
                break

    return traders

# ── Step 2: Profile each wallet ───────────────────────────────────────────────

def profile_balance(address: str, sm_tokens: set[str], chain: str = CHAIN) -> tuple[int, float, int]:
    """
    Returns (score/40, total_portfolio_usd, sm_overlap_count)
    Score = portfolio size (20pts) + smart money token overlap (20pts)
    """
    data = nansen(f"research profiler balance --address {address} --chain {chain} --limit 20 --fields token_symbol,value_usd")
    if not data or not data.get("success"):
        return 0, 0.0, 0

    rows = data.get("data", {}).get("data", data.get("data", []))
    if isinstance(rows, dict): rows = rows.get("data", [])

    total_usd    = sum(f(r.get("value_usd")) for r in rows)
    held_symbols = {r.get("token_symbol", "") for r in rows}
    overlap      = len(held_symbols & sm_tokens)

    # Portfolio size score (up to 20 pts)
    if   total_usd > 10_000_000: port_pts = 20
    elif total_usd > 1_000_000:  port_pts = 16
    elif total_usd > 100_000:    port_pts = 10
    elif total_usd > 10_000:     port_pts = 5
    else:                        port_pts = 1

    # Smart money alignment (up to 20 pts)
    align_pts = min(overlap * 4, 20)

    return port_pts + align_pts, total_usd, overlap

def profile_transactions(address: str, chain: str = CHAIN) -> tuple[int, int, float]:
    """
    Returns (score/30, tx_count, total_volume_usd)
    """
    data = nansen(f"research profiler transactions --address {address} --chain {chain} --days 30 --limit 50 --fields volume_usd,source_type")
    if not data or not data.get("success"):
        return 0, 0, 0.0

    rows = data.get("data", {}).get("data", data.get("data", []))
    if isinstance(rows, dict): rows = rows.get("data", [])

    count  = len(rows)
    volume = sum(f(r.get("volume_usd")) for r in rows)

    if   count > 40: pts = 30
    elif count > 20: pts = 22
    elif count > 10: pts = 14
    elif count > 5:  pts = 8
    else:            pts = max(count, 0) * 1

    return pts, count, volume

def profile_pnl(address: str, chain: str = CHAIN) -> tuple[int, float]:
    """Returns (score/30, realized_pnl_usd)"""
    data = nansen(f"research profiler pnl-summary --address {address} --chain {chain} --days 30")
    if not data or not data.get("success"):
        return 0, 0.0

    d   = data.get("data", {})
    if isinstance(d, dict) and "data" in d: d = d.get("data", [{}])[0] if d.get("data") else {}
    if isinstance(d, list): d = d[0] if d else {}

    pnl = f(d.get("realized_pnl_usd"))
    if   pnl > 1_000_000: pts = 30
    elif pnl > 100_000:   pts = 22
    elif pnl > 10_000:    pts = 14
    elif pnl > 1_000:     pts = 7
    elif pnl > 0:         pts = 3
    else:                 pts = 0
    return pts, pnl

# ── Step 3: Generate gitlawb DID ─────────────────────────────────────────────

def make_did(tag: str) -> str:
    dir_path = f"/tmp/gitlawb-poc-{tag}"
    Path(dir_path).mkdir(exist_ok=True)
    gl(f"identity new --dir {dir_path} --force")
    did = gl(f"identity show --dir {dir_path}")
    return did if did.startswith("did:key:") else "did:key:[generated]"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 72)
    print("   gitlawb × Nansen  ·  SMART DEVELOPER INTELLIGENCE")
    print("   Nansen CLI Hackathon PoC  —  March 2026")
    print("=" * 72)
    print("""
   Every gitlawb repo owner has a cryptographic DID (Ed25519).
   When a developer links their DID to a wallet, we can ask Nansen:
   "Is this contributor Smart Money?"

   This PoC pulls live Nansen Smart Money traders, profiles their
   on-chain activity, and shows what their gitlawb contributor
   score would look like — in real time.
""")

    # ── 1. Smart money context ────────────────────────────────────────────────
    print("  [1/4] Smart Money context...")

    sm_tokens  = get_smart_money_tokens()
    sm_netflow = get_smart_money_netflow()

    if sm_netflow:
        print(f"        Top tokens smart money is buying (7d net inflow):")
        for r in sm_netflow:
            nf = f(r.get("net_flow_7d_usd"))
            tc = r.get("trader_count", "?")
            sym = r.get("token_symbol", "?")
            sign = "+" if nf >= 0 else ""
            print(f"          {sym:<12}  {sign}${nf:>14,.0f}   ({tc} traders)")
    print()

    # ── 2. Get trader addresses ───────────────────────────────────────────────
    print("  [2/4] Fetching live Smart Money DEX traders...")
    traders = get_trader_addresses()
    if not traders:
        print("  ERROR: could not fetch traders — check API key")
        sys.exit(1)
    print(f"        Found {len(traders)} unique smart money wallets\n")

    # ── 3. Profile each trader ────────────────────────────────────────────────
    print("  [3/4] Profiling wallets + generating gitlawb DIDs...")
    print()

    results = []
    for i, t in enumerate(traders):
        addr  = t["address"]
        label = t["label"]
        repo  = REPOS[i % len(REPOS)]
        short = addr[:6] + "..." + addr[-4:]

        print(f"       ▸ {label}  ({short})")

        # Generate real gitlawb DID
        did = make_did(f"wallet-{i}")
        print(f"         DID   → {did[:52]}...")

        chain = t.get("chain", CHAIN)
        port_pts, portfolio_usd, overlap = profile_balance(addr, sm_tokens, chain)
        tx_pts, tx_count, volume_usd     = profile_transactions(addr, chain)
        pnl_pts, pnl_usd                 = profile_pnl(addr, chain)
        total = port_pts + tx_pts + pnl_pts

        print(f"         Score → {total}/100  (portfolio:{port_pts}  activity:{tx_pts}  pnl:{pnl_pts})")
        print(f"                 portfolio ${portfolio_usd:,.0f}  |  {tx_count} txs/30d  |  SM overlap: {overlap} tokens")
        print()

        results.append({
            "label":   label,
            "address": addr,
            "short":   short,
            "repo":    repo,
            "did":     did,
            "bought":  t["bought"],
            "portfolio_usd": portfolio_usd,
            "volume_usd":    volume_usd,
            "tx_count":      tx_count,
            "overlap":       overlap,
            "pnl_usd":       pnl_usd,
            "port_pts":      port_pts,
            "tx_pts":        tx_pts,
            "pnl_pts":       pnl_pts,
            "total":         total,
        })

    results.sort(key=lambda x: x["total"], reverse=True)

    # ── 4. Leaderboard ────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print("   SMART DEVELOPER LEADERBOARD")
    print("   Scoring: portfolio(40) · on-chain activity(30) · PnL(30)")
    print("=" * 72)
    print()

    medals = ["1st", "2nd", "3rd", "4th", "5th"]
    print(f"   {'':4}  {'WALLET LABEL':<28} {'SCORE':>5}  {'PORTFOLIO':>14}  {'TXs':>4}  {'SM OVERLAP':>10}")
    print("   " + "─" * 68)
    for i, r in enumerate(results):
        print(f"   {medals[i]:<4}  {r['label'][:27]:<28} {r['total']:>3}/100  ${r['portfolio_usd']:>13,.0f}  {r['tx_count']:>4}  {r['overlap']:>5} tokens")

    print()
    print("   SCORE BREAKDOWN  (port/40 · activity/30 · pnl/30)")
    print("   " + "─" * 68)
    print(f"   {'WALLET':<28}  {'GITLAWB REPO':<30} {'PRT':>3} {'ACT':>3} {'PNL':>3} {'TOT':>4}")
    print("   " + "─" * 68)
    for r in results:
        print(f"   {r['label'][:27]:<28}  {r['repo']:<30} {r['port_pts']:>3} {r['tx_pts']:>3} {r['pnl_pts']:>3} {r['total']:>4}")

    print()
    print("   GITLAWB DIDs  (real Ed25519 cryptographic identities)")
    print("   " + "─" * 68)
    for r in results:
        print(f"   {r['short']:<14}  {r['did'][:55]}...")

    print()
    print("=" * 72)
    print("   HOW THIS WORKS IN PRODUCTION")
    print("=" * 72)
    print("""
   1. Developer pushes code to gitlawb:
        git clone gitlawb://did:key:z6Mk.../defi-core

      → Auth via HTTP Signature (RFC 9421) + Ed25519 DID keypair

   2. Developer links their DID to an ETH wallet address
      (signed attestation stored as UCAN capability token)

   3. Any agent or DAO queries via gitlawb MCP:
        gl mcp serve → tool: smart_developer_score(did)

      → internally calls Nansen CLI:
          nansen research profiler balance      --address <wallet>
          nansen research profiler transactions --address <wallet>
          nansen research profiler pnl-summary  --address <wallet>
          nansen research smart-money holdings  (for SM alignment)

   4. Result: on-chain credibility score for every repo owner.
      Not just GitHub stars — real skin in the game.

   USE CASES:
      • DAO treasuries: fund contributors with highest SM scores
      • Protocol bug bounties: weight rewards by on-chain credibility
      • Token-gated repos: only wallets with X score can push
      • AI agent trust: higher SM score = higher autonomy level
""")
    print(f"   Total Nansen API calls: {len(api_calls)}")
    print()
    print("=" * 72)

if __name__ == "__main__":
    if not os.environ.get("NANSEN_API_KEY"):
        print("ERROR: set NANSEN_API_KEY first")
        sys.exit(1)
    main()

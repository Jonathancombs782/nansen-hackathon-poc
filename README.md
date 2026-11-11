# gitlawb × Nansen: Smart Developer Intelligence

**Nansen CLI Hackathon submission — Week 1, March 2026**

## What it does

Pulls live Smart Money wallets from Nansen, profiles their on-chain activity,
and generates a real gitlawb DID (Ed25519) for each — producing a ranked
**Smart Developer Leaderboard**: on-chain credibility scores for crypto OSS contributors.

> Note: the repo names paired with wallets in the leaderboard output
> (e.g. `defi-core/yield-optimizer`) are **fictional demo data** for the
> hackathon, not real gitlawb repositories.

Not just GitHub stars. Real skin in the game.

## Prerequisites

- Python 3.10+
- `nansen-cli` — install globally: `npm install -g nansen-cli` (version unpinned;
  the script assumes its current JSON output shape)
- `gl` (gitlawb CLI) — build from source: `git clone https://github.com/gitlawb/gitlawb`
  then `cargo build --release`; put `target/release/gl` on your `PATH`,
  or point `GL_BIN` at it
- A paid Nansen API key — export it as `NANSEN_API_KEY` (the script exits
  if the key is unset or Nansen reports `CREDITS_EXHAUSTED`)

## How to run

```bash
npm install -g nansen-cli
export NANSEN_API_KEY=<your_key>
python3 smart_dev_score.py
```

## Scoring (100 pts)

| Signal | Points | Source |
|--------|--------|--------|
| Portfolio size | 40 | `nansen research profiler balance` |
| On-chain activity (30d txs) | 30 | `nansen research profiler transactions` |
| Realized PnL | 30 | `nansen research profiler pnl-summary` |

Smart Money context pulled from:
- `nansen research smart-money dex-trades` — live trader discovery
- `nansen research smart-money netflow` — what SM is buying
- `nansen research smart-money holdings` — SM token alignment

## Architecture

```
nansen smart-money dex-trades   ← find active SM wallets
        ↓
nansen profiler balance         ← portfolio size + SM token overlap
nansen profiler transactions    ← on-chain activity score
nansen profiler pnl-summary     ← realized PnL score
        ↓
gl identity new                 ← generate real Ed25519 DID per wallet
        ↓
Smart Developer Leaderboard     ← ranked output
```

In production, gitlawb developers link their DID to a wallet address
(signed UCAN capability token). Any agent or DAO can then query:

```
gl mcp serve → tool: smart_developer_score(did)
```

## gitlawb

A decentralized, AI-agent-first GitHub alternative. Every repo is
DID-authenticated. Git objects stored on IPFS → Filecoin → Arweave.
Auth via HTTP Signatures (RFC 9421) + UCAN capabilities.

→ https://github.com/gitlawb/gitlawb

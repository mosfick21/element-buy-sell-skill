<div align="center">

# Element Market Skill

**List, buy and price NFTs on Element Market (BNB Chain) from an AI agent. No paid API key.**

![chain](https://img.shields.io/badge/chain-BNB%20Chain-F0B90B) ![python](https://img.shields.io/badge/python-3.10%2B-3776AB) ![wallet](https://img.shields.io/badge/wallet-Binance%20Agentic%20Wallet-black) ![license](https://img.shields.io/badge/license-MIT-green)

</div>

## Contents
- [What it is](#what-it-is) · [How it works](#how-it-works) · [Quick start](#quick-start) · [Usage](#usage) · [Example](#example-output) · [Security](#security) · [FAQ](#faq)

## What it is

| | |
|---|---|
| Market | Element Market, BNB Chain |
| Signer | Binance Agentic Wallet CLI (`baw`), keys never leave it |
| Auth | Element web app public key, no paid OpenAPI key |
| Format | Agent skill (`SKILL.md`) + one Python CLI |

## How it works

```
 agent ──> em.py ──> Element API (orders, GraphQL)
             │
             └──> baw ──> sign EIP-712 / send tx ──> ElementEx contract
```

1. Reads (floor, item, listings) go through Element's GraphQL.
2. **List**: fetch nonce + fees, build the BatchSignedERC721 order, sign it with baw, verify the signer, post it.
3. **Buy**: fetch the order's exchange data, encode the fill locally, simulate, send with baw.
4. Nothing is sent without `--send`.

## Features
- Gasless listing (one-time approval per collection)
- Buy any BNB-priced ERC721 listing by order id
- Mixed-currency floor (BNB and USDT listings)
- Dry run by default, simulation before every send

## Quick start
```bash
git clone https://github.com/<you>/element-market-skill && cd element-market-skill
pip install eth-account eth-abi eth-utils
mkdir -p ~/.config/element-market && cp wallets.example.json ~/.config/element-market/wallets.json  # put your agent wallet
python3 scripts/em.py floor snakeid 3
```

## Usage

| Command | Description |
|---|---|
| `floor <slug> [n]` | cheapest listings |
| `item <nft> <tokenId>` | asset info, best ask/bid |
| `mine <wallet>` | your active listings |
| `list <wallet> <nft> <tokenId> <priceBNB> [--days N] [--send]` | list an NFT |
| `buy <wallet> <orderId> [--send]` | buy a listing |
| `cancel <wallet> <nonce> [--send]` | cancel a listing |

| Env | Default |
|---|---|
| `EM_WALLETS` | `~/.config/element-market/wallets.json` |
| `EM_BAW_DIR` | `~/.baw-{name}` |
| `EM_BAW_BIN` | `baw` |
| `BSC_RPC` | public BNB Chain RPC |

## Example output
```json
{
 "priceBNB": 0.00038,
 "platformFeeBps": 200,
 "royaltyBps": 500,
 "youGetBNB": 0.0003534,
 "approved": true,
 "ok": true,
 "post": {"successList": [{"assetTokenId": "3079", "orderId": "4057..."}]}
}
```

## Security
- No private keys: every signature and tx goes through `baw`.
- `wallets.json` holds addresses only and is git-ignored.
- Dry run unless `--send`.

## FAQ
<details><summary>Do I need an Element API key?</summary>No. The tool uses the same public key as the element.market website.</details>
<details><summary>Does listing cost gas?</summary>No. Only the first approval per collection is an on-chain tx.</details>
<details><summary>What if Element changes its key?</summary>Set <code>ELEMENT_SITE_KEY</code> and <code>ELEMENT_SITE_SECRET</code> from the site's <code>element-sdk-*.js</code>. See SKILL.md.</details>

## Requirements
Python 3.10+, `eth-account`, `eth-abi`, `eth-utils`, Binance Agentic Wallet CLI.

<sub>Unofficial tool. Not affiliated with Element or Binance. Use at your own risk.</sub>

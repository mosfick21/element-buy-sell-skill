---
name: element-market
description: "Use when buying, listing, cancelling or pricing NFTs on Element Market (BNB Chain) through a Binance Agentic Wallet. No paid Element API key needed."
---

# Element Market (BNB Chain), no API key

Tool: `python3 scripts/em.py <cmd>` (path relative to this skill). It prints JSON.
Without `--send` it signs and sends nothing; it only builds and simulates. Show the dry-run result to the user first and send only after a clear go-ahead.

| Cmd | What |
|---|---|
| `floor <slug> [n]` | cheapest BUY_NOW listings: price, paymentToken, orderId, maker |
| `item <nft> <tokenId>` | name, best ask/bid, collection slug, royalty |
| `mine <wallet>` | the wallet's active Element listings |
| `buy <wallet> <orderId> [--send]` | build the fill tx, simulate, send through baw |
| `list <wallet> <nft> <tokenId> <priceBNB> [--days N] [--send]` | approve if needed, sign with baw, verify signer, post |
| `cancel <wallet> <nonce> [--send]` | cancel one listing by its nonce |
| `accept <wallet> <nft> <tokenId> [probeIds...] [--min BNB] [--send]` | sell into the best WBNB offer: approve if needed, simulate, send. Fresh mints not yet indexed: pass other token ids of the same collection as probeIds (collection offers fit any token) |

## Setup
1. Install and log in to the Binance Agentic Wallet CLI (`baw`), one profile dir per wallet (default `~/.baw-<name>`, override with `EM_BAW_DIR`).
2. Create `~/.config/element-market/wallets.json` (override with `EM_WALLETS`):
   `{"main": "0xYourAgentWallet"}` or `{"main": {"address": "0x...", "bawDir": "/path/to/baw/profile"}}`
3. `pip install eth-account eth-abi eth-utils`. Optional: `BSC_RPC` (default public BNB Chain RPC).

## How it works
- Auth: the public key the element.market web app itself uses. `X-Api-Sign = HMAC_SHA256(secret, key+nonce+ts) + ".nonce.ts"`. `/openapi/*` rejects this key; use `/v3/*`, `/v1/*` and `/graphql?args=<Op>`.
- Reads go through GraphQL (`searchV2`, `asset`, `accountOrdersV3`). Variables need non-null types (`SearchInput!`, `AccountOrderInput!`). Page size max 50.
- Buy: `/v3/orders/getOrderExchangeDataByOrderId` returns `exchangeData` (a BatchSignedERC721 order), encoded locally into `fillBatchSignedERC721Order`. Native BNB is `0xeeee...eeee` in calldata; the zero address reverts with `invalid erc20Token`.
- List: `getMakerNonce` (needs `exchange`), `confData.oracleSignature`, `ElementEx.getHashNonce(maker)`. Sign the `BatchSignedERC721Orders` EIP-712 with baw `eth_signTypedData_v4`, check the signature recovers to the maker, then `POST /v3/orders/postBatch`.
- Fees: platform fee and royalty come from a live listing in the same collection (default 200 bps).

## Pitfalls
- Prices are mixed currency: listings can be BNB or USDT. The PriceLowToHigh sort and `collectionFloorPrice` mix tokens. Convert each listing to USD before comparing; never treat a raw `price` as BNB.
- baw parses typed data in JS: integers above 2^53 fail with "System abnormality". The tool sends every message integer as a decimal string.
- With `oracleSignature=1` a listing cannot be fill-simulated before posting (Element adds the oracle extraData at fill time). After posting, `buy <other wallet> <orderId>` without `--send` simulates a real fill.
- If the site key rotates (`X-api-key is not available`), open any element.market asset page, fetch `element-sdk-*.js`, find `opts()` and set `ELEMENT_SITE_KEY` / `ELEMENT_SITE_SECRET`.
- `/v1/orders/confData` sometimes times out; the tool falls back to `oracleSignature=1`.
- An NFT escrowed on another market is not owned by the wallet, so `list` reports "not owner".
- Supported: BNB-priced ERC721. USDT listings and ERC1155 are not wired yet.

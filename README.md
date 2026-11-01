<div align="center">

<img src="assets/element.jpeg" alt="Element Market" width="100%"/>

# element-buy-sell-skill

Buy and sell NFTs on Element Market from your **Binance Agentic Wallet**.

**No private key · No API key · Just your agent wallet.**

![BNB Chain](https://img.shields.io/badge/BNB_Chain-F0B90B?style=flat-square&logo=binance&logoColor=black)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Binance Agentic Wallet](https://img.shields.io/badge/Binance-Agentic_Wallet-F0B90B?style=flat-square&logo=binance&logoColor=black)
![No API Key](https://img.shields.io/badge/API_Key-Not_Needed-22c55e?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)

</div>

---

## Install

```bash
npx github:mosfick21/element-buy-sell-skill
```

Or manually:

```bash
git clone https://github.com/mosfick21/element-buy-sell-skill
cd element-market-skill
pip install eth-account eth-abi eth-utils
```

Add your agent wallet:

```bash
mkdir -p ~/.config/element-market
echo '{"main": "0xYourAgentWallet"}' > ~/.config/element-market/wallets.json
```

## Commands

| Command | Action |
|---|---|
| `floor <slug> [n]` | Cheapest listings |
| `item <nft> <id>` | Asset, best ask / bid |
| `mine <wallet>` | Your active listings |
| `list <wallet> <nft> <id> <bnb> [--send]` | List an NFT |
| `buy <wallet> <orderId> [--max bnb] [--send]` | Buy a listing (`--send` needs `--max`) |
| `cancel <wallet> <nonce> [--send]` | Cancel a listing |
| `accept <wallet> <nft> <id> [probeIds] [--min bnb] [--single] [--send]` | Sell into the best offer (`--send` needs `--min`) |
| `revoke <wallet> <nft> [--send]` | Remove Element's approval for a collection |

```bash
python3 scripts/em.py list main 0xNFT 3079 0.0004 --send
```

Without `--send`, nothing is signed or sent.

## Output

```json
{
  "priceBNB": 0.00038,
  "youGetBNB": 0.0003534,
  "approved": true,
  "ok": true,
  "orderId": "4057243579547595328"
}
```

## Safety

- Nothing is signed or sent without `--send`.
- `buy --send` refuses to run without a `--max` price cap; `accept --send` refuses without a `--min` floor.
- Selling needs Element's exchange to be approved for the NFT. By default that is collection-wide (`setApprovalForAll`), like every NFT market. Use `accept --single` to approve only the one token, and `revoke` to remove a collection approval when you are done.
- No private key or seed phrase is ever read. Signing goes through the Binance Agentic Wallet CLI.
- The Element web key in the script is the public key shipped in element.market's own JavaScript, not a user secret.

## Config

| Env | Default |
|---|---|
| `EM_WALLETS` | `~/.config/element-market/wallets.json` |
| `EM_BAW_DIR` | `~/.baw-{name}` |
| `EM_BAW_BIN` | `baw` |
| `BSC_RPC` | Public BNB Chain RPC |

## Notes

- Listing is gasless. Only the first approval per collection costs gas.
- Built for the Binance Agentic Wallet. It signs every order and tx, so no private key is stored anywhere.
- No Element API key needed.
- `wallets.json` holds addresses only.
- BNB-priced ERC-721 is supported.

---

<div align="right"><sub><b>DYOR.</b> Unofficial. Not affiliated with Element or Binance.</sub></div>

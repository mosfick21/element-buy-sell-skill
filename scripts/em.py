#!/usr/bin/env python3
"""Element Market (BSC) without a paid API key. Signs and sends through baw.

Usage (CLI, prints JSON):
  em.py floor  <slug> [n]                    cheapest BUY_NOW listings of a collection
  em.py item   <nft> <tokenId>               asset info + best ask/bid + collection fees
  em.py mine   <wallet>                      wallet's active Element listings
  em.py buy    <wallet> <orderId> [--send]   build buy tx, simulate; --send executes via baw
  em.py list   <wallet> <nft> <tokenId> <priceBNB> [--days N] [--send]
                                             approve check + sign + post a BNB listing
  em.py cancel <wallet> <nonce> [--send]     cancel one of our listings by its nonce

Without --send nothing is signed or sent: it only builds and simulates.
Wallet = a name from the wallets file (see load_wallets). Each name maps to a Binance Agentic
Wallet (baw) profile dir, default ~/.baw-<name>.
"""
import hashlib, hmac, json, os, random, subprocess, sys, time, urllib.request

from eth_abi import encode as abi_encode
from eth_account.messages import encode_typed_data
from eth_utils import keccak

WALLETS_FILE = os.path.expanduser(os.environ.get("EM_WALLETS", "~/.config/element-market/wallets.json"))
BAW_DIR_TEMPLATE = os.environ.get("EM_BAW_DIR", "~/.baw-{name}")


def load_wallets():
    """wallets.json: {"main": "0xabc..."} or {"main": {"address": "0xabc...", "bawDir": "~/.baw-main"}}"""
    try: raw = json.load(open(WALLETS_FILE))
    except FileNotFoundError: return {}, {}
    addr, dirs = {}, {}
    for n, v in raw.items():
        if isinstance(v, str): addr[n] = v
        else: addr[n] = v["address"]; dirs[n] = v.get("bawDir")
        dirs[n] = os.path.expanduser(dirs.get(n) or BAW_DIR_TEMPLATE.format(name=n))
    return addr, dirs


WALLETS, BAW_DIRS = load_wallets()
RPC = os.environ.get("BSC_RPC", "https://bsc-dataseed.bnbchain.org")
API = "https://api.element.market"
# Element web app's own public key + HMAC secret (from element-sdk-*.js opts()).
# If calls start failing with "X-api-key is not available", re-extract them (see SKILL.md).
SITE_KEY = os.environ.get("ELEMENT_SITE_KEY", "zQbYj7RhC1VHIBdWU63ki5AJKXloamDT")
SITE_SECRET = os.environ.get("ELEMENT_SITE_SECRET", "UqCMpfGn3VyQEdsjLkzJv9tNlgbKFD7O")
CHAIN_MID = 201
CHAIN_ID = 56
EX = "0xb3e3DfCb2d9f3DdE16d78B9e6EB3538Eb32B5ae1"   # ElementEx (BSC)
NATIVE = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
ZERO = "0x" + "0" * 40
DEFAULT_FEE_BPS = 200
DEFAULT_FEE_RECIPIENT = "0x67c0a1fc3ec90aaa393adaea9cbe7230df3ec7ad"
BAW_BIN = os.environ.get("EM_BAW_BIN", "baw")

BO = ("fragment BasicOrder on OrderV3Type { orderId chainMId expirationTime listingTime maker taker side "
      "saleKind paymentToken quantity price standard contractAddress tokenId schema }")


# ------------------------------------------------------------------ low level
def sel(sig):
    return "0x" + keccak(text=sig).hex()[:8]


def _headers(extra=None):
    n = random.randint(1000, 9999); ts = int(time.time())
    sig = hmac.new(SITE_SECRET.encode(), f"{SITE_KEY}{n}{ts}".encode(), hashlib.sha256).hexdigest()
    h = {"X-Api-Key": SITE_KEY, "X-Api-Sign": f"{sig}.{n}.{ts}", "X-Viewer-Chainmid": str(CHAIN_MID),
         "Content-Type": "application/json", "User-Agent": "Mozilla/5.0",
         "Origin": "https://element.market", "Referer": "https://element.market/"}
    if extra: h.update(extra)
    return h


def api(path, body=None, timeout=35):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=_headers())
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    if r.get("code") not in (0, None):
        raise RuntimeError(f"element {path}: {r.get('code')} {r.get('message') or r.get('msg')}")
    return r.get("data", r)


def gql(op, query, variables):
    req = urllib.request.Request(API + "/graphql?args=" + op, headers=_headers({"x-query-args": op}),
                                 data=json.dumps({"operationName": op, "query": query, "variables": variables}).encode())
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if r.get("errors"): raise RuntimeError(f"graphql {op}: {r['errors'][0].get('message')}")
    return r["data"]


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def eth_call(frm, to, data, value=0):
    return rpc("eth_call", [{"from": frm, "to": to, "data": data, "value": hex(value)}, "latest"])


def baw(wallet, *args):
    if wallet not in WALLETS: raise SystemExit(f"unknown wallet '{wallet}', add it to {WALLETS_FILE}")
    env = dict(os.environ, BINANCE_BAW_DIR=BAW_DIRS[wallet])
    r = subprocess.run([BAW_BIN, *args], capture_output=True, text=True, timeout=120, cwd=os.path.expanduser("~"), env=env)
    try: return json.loads(r.stdout)
    except Exception: return {"raw": (r.stdout or r.stderr)[:300]}


def baw_send(wallet, to, data, value=0):
    p = baw(wallet, "contract-call", "preview", "--binanceChainId", "56", "--from", WALLETS[wallet], "--to", to,
            "--value", str(value), "--inputData", data, "--json")
    rid = (p.get("data") or {}).get("requestId")
    if not rid: raise RuntimeError("baw preview failed: " + json.dumps(p)[:300])
    e = baw(wallet, "contract-call", "execute", "--requestId", rid, "--json")
    tx = (e.get("data") or {}).get("txHash")
    if not tx: raise RuntimeError("baw execute failed: " + json.dumps(e)[:300])
    for _ in range(40):
        rc = rpc("eth_getTransactionReceipt", [tx]).get("result")
        if rc:
            fee = int(rc["gasUsed"], 16) * int(rc["effectiveGasPrice"], 16) / 1e18
            return {"tx": tx, "ok": rc["status"] == "0x1", "gwei": int(rc["effectiveGasPrice"], 16) / 1e9, "feeBNB": fee}
        time.sleep(1.5)
    return {"tx": tx, "ok": None}


def _strnums(o):
    # baw parses JSON in JS: ints above 2^53 lose precision, so send every int as a decimal string
    if isinstance(o, bool): return o
    if isinstance(o, int): return str(o)
    if isinstance(o, dict): return {k: (v if k == "chainId" else _strnums(v)) for k, v in o.items()}
    if isinstance(o, list): return [_strnums(x) for x in o]
    return o


def baw_sign_typed(wallet, typed):
    t = dict(typed); t["message"] = _strnums(typed["message"])
    msg = json.dumps({"method": "eth_signTypedData_v4", "params": [WALLETS[wallet], json.dumps(t)]})
    p = baw(wallet, "sign-message", "preview", "--binanceChainId", "56", "--signType", "EIP712", "--message", msg, "--json")
    rid = (p.get("data") or {}).get("requestId")
    if not rid: raise RuntimeError("baw sign preview failed: " + json.dumps(p)[:300])
    e = baw(wallet, "sign-message", "execute", "--requestId", rid, "--json")
    d = e.get("data") or {}
    sig = d.get("signature")
    if not sig: raise RuntimeError("baw sign execute failed: " + json.dumps(e)[:300])
    sig = sig if sig.startswith("0x") else "0x" + sig
    raw = bytes.fromhex(sig[2:])
    r, s = "0x" + raw[:32].hex(), "0x" + raw[32:64].hex()
    v = raw[64] if len(raw) >= 65 else int(d.get("signatureRecovery", "0x1b"), 16)
    if v < 27: v += 27
    return v, r, s


def bits(parts):
    out = ""
    for v, n in parts:
        if isinstance(v, str): v = int(v, 16) if v.lower().startswith("0x") else int(v)
        out += format(int(v) & ((1 << n) - 1), "0%dx" % (n // 4))
    return "0x" + out


def ctok(a):    # standard -> contract payment token
    return NATIVE if int(a, 16) == 0 else a.lower()


# ------------------------------------------------------------------ reads
def floor(slug, n=5):
    q = ("query S($first:Int,$search:SearchInput!){ searchV2(first:$first, search:$search){ totalCount edges { node { asset { "
         "tokenId name orderData { bestAsk { ...BasicOrder } } } } } } } " + BO)
    d = gql("S", q, {"first": n, "search": {"collectionSlugs": [slug], "sortBy": "PriceLowToHigh", "sortAscending": True,
                                           "blockChains": [{"chain": "bsc", "chainId": "0x38"}], "toggles": ["BUY_NOW"]}})
    out = []
    for e in d["searchV2"]["edges"]:
        a = e["node"]["asset"]; o = (a.get("orderData") or {}).get("bestAsk") or {}
        out.append({"tokenId": a["tokenId"], "name": a["name"], "price": o.get("price"), "orderId": o.get("orderId"),
                    "maker": o.get("maker"), "paymentToken": o.get("paymentToken")})
    return {"listed": d["searchV2"]["totalCount"], "cheapest": out}


def item(nft, token_id):
    q = ("query AssetsDetail($blockChain: BlockChainInput!, $contractAddress: Address!, $tokenId: String!) { asset(identity:"
         "{blockChain:$blockChain, contractAddress:$contractAddress, tokenId:$tokenId}) { name orderData { bestAsk { ...BasicOrder } "
         "bestBid { ...BasicOrder } } collection { name slug royalty royaltyAddress } } } " + BO)
    return gql("AssetsDetail", q, {"blockChain": {"chain": "bsc", "chainId": "0x38"}, "contractAddress": nft, "tokenId": str(token_id)})["asset"]


def mine(wallet):
    addr = WALLETS.get(wallet, wallet).lower()
    q = "query A($first:Int,$input:AccountOrderInput!){ accountOrdersV3(first:$first, input:$input){ edges { node { ...BasicOrder } } } } " + BO
    d = gql("A", q, {"first": 50, "input": {"identity": {"address": addr, "blockChain": {"chain": "bsc", "chainId": "0x38"}}, "orderType": 1}})
    return [e["node"] for e in d["accountOrdersV3"]["edges"]]


def collection_fees(nft, token_id=None):
    """Platform fee comes from a live listing of the same collection; royalty from GraphQL."""
    fee_bps, fee_to, roy_bps, roy_to = DEFAULT_FEE_BPS, DEFAULT_FEE_RECIPIENT, 0, ZERO
    try:
        a = item(nft, token_id or 1); c = a.get("collection") or {}
        if c.get("royalty") and c.get("royaltyAddress"):
            roy_bps, roy_to = int(round(float(c["royalty"]) * (100 if float(c["royalty"]) < 100 else 1))), c["royaltyAddress"].lower()
        slug = c.get("slug")
        if slug:
            for x in floor(slug, 1)["cheapest"]:
                if x.get("orderId"):
                    ed = json.loads(api("/v3/orders/getOrderExchangeDataByOrderId",
                                        [{"chainMid": CHAIN_MID, "orderId": x["orderId"], "buyer": ZERO}])[0]["exchangeData"])
                    bc = (ed.get("basicCollections") or ed.get("collections"))[0]
                    fee_bps, fee_to = int(bc["platformFee"]), ed["platformFeeRecipient"].lower()
                    roy_bps, roy_to = int(bc["royaltyFee"]), bc["royaltyFeeRecipient"].lower()
    except Exception:
        pass
    return fee_bps, fee_to, roy_bps, roy_to


# ------------------------------------------------------------------ buy
def encode_fill(ed, taker):
    """Calldata for ElementEx.fillBatchSignedERC721Order for the item at ed['nonce']."""
    tk = int(taker, 16); hi, lo = tk >> 96, tk & ((1 << 96) - 1)
    flags = 0; extra = (ed.get("extraData") or "0x")[2:]
    if extra: extra += format(len(extra) // 2, "08x"); flags |= 128
    if int(ed.get("oracleSignature") or 0) == 1: flags |= 1
    pt = ctok(ed["paymentToken"])
    d1 = bits([(ed.get("signatureType") or 0, 8), (flags, 8), (ed["startNonce"], 40), (ed["v"], 8), (ed["listingTime"], 32), (ed["maker"], 160)])
    d2 = bits([(hi, 64), (ed["expirationTime"], 32), (pt, 160)])
    d3 = bits([(lo, 96), (ed["platformFeeRecipient"], 160)])
    want = int(ed["nonce"]); x = int(ed["startNonce"]); col = ""; value = 0
    for kind, lst in ((0, ed.get("basicCollections") or []), (1, ed.get("collections") or [])):
        for c in lst:
            items = c["items"]; s = x; x += len(items)
            idx = [want - s] if s <= want < s + len(items) else []
            e = "".join(format(i, "02x") for i in idx) + "00" * (16 - len(idx))
            for i in idx: value += int(items[i]["erc20TokenAmount"])
            col += bits([(int(e[:24], 16), 96), (c["nftAddress"], 160)])[2:]
            col += bits([(kind, 8), (len(items), 8), (len(idx), 8), (0, 8), (int(e[24:], 16), 32),
                         (c["platformFee"], 16), (c["royaltyFee"], 16), (c["royaltyFeeRecipient"], 160)])[2:]
            for it in items:
                if kind == 0: col += bits([(int(it["erc20TokenAmount"]), 96), (int(it["nftId"]), 160)])[2:]
                else: col += bits([(int(it["erc20TokenAmount"]), 256)])[2:] + bits([(int(it["nftId"]), 256)])[2:]
    col += extra
    L = len(col) // 2
    data = (sel("fillBatchSignedERC721Order((uint256,uint256,uint256,bytes32,bytes32),bytes)") + d1[2:] + d2[2:] + d3[2:]
            + bits([(ed["r"], 256)])[2:] + bits([(ed["s"], 256)])[2:] + format(6 * 32, "064x") + format(L, "064x")
            + col + "00" * ((32 - L % 32) % 32))
    if pt != NATIVE: value = 0
    return data, value


def buy(wallet, order_id, send=False):
    me = WALLETS[wallet]
    o = api("/v3/orders/getOrderExchangeDataByOrderId", [{"chainMid": CHAIN_MID, "orderId": str(order_id), "buyer": me.lower()}])[0]
    if not o.get("isValid"): return {"ok": False, "error": "order not valid: " + str(o.get("errorDetail"))}
    ed = json.loads(o["exchangeData"])
    if "basicCollections" not in ed and "collections" not in ed:
        return {"ok": False, "error": "unsupported order type (not a batch-signed ERC721 listing)"}
    data, value = encode_fill(ed, me)
    if ctok(ed["paymentToken"]) != NATIVE: return {"ok": False, "error": "only BNB-priced listings are supported"}
    bal = int(rpc("eth_getBalance", [me, "latest"])["result"], 16)
    sim = eth_call(me, EX, data, value)
    res = {"nft": o["contractAddress"], "tokenId": o["tokenId"], "priceBNB": value / 1e18, "balanceBNB": bal / 1e18,
           "simulate": "OK" if "result" in sim else sim.get("error", {}).get("message", "")[:160]}
    if send and "result" in sim: res.update(baw_send(wallet, EX, data, value))
    return res


# ------------------------------------------------------------------ list
BS_TYPES = {
    "EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                     {"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
    "BatchSignedERC721Orders": [
        {"type": "address", "name": "maker"}, {"type": "uint256", "name": "listingTime"}, {"type": "uint256", "name": "expiryTime"},
        {"type": "uint256", "name": "startNonce"}, {"type": "address", "name": "erc20Token"}, {"type": "address", "name": "platformFeeRecipient"},
        {"type": "BasicCollection[]", "name": "basicCollections"}, {"type": "Collection[]", "name": "collections"},
        {"type": "uint256", "name": "hashNonce"}],
    "BasicCollection": [{"type": "address", "name": "nftAddress"}, {"type": "bytes32", "name": "fee"}, {"type": "bytes32[]", "name": "items"}],
    "Collection": [{"type": "address", "name": "nftAddress"}, {"type": "bytes32", "name": "fee"}, {"type": "OrderItem[]", "name": "items"}],
    "OrderItem": [{"type": "uint256", "name": "erc20TokenAmount"}, {"type": "uint256", "name": "nftId"}],
}


def is_approved(owner, nft):
    r = eth_call(owner, nft, sel("isApprovedForAll(address,address)") + owner[2:].lower().zfill(64) + EX[2:].lower().zfill(64))
    return int(r.get("result", "0x0") or "0x0", 16) == 1


def owner_of(nft, tid):
    r = eth_call(ZERO, nft, sel("ownerOf(uint256)") + format(int(tid), "064x"))
    return ("0x" + r["result"][26:]).lower() if r.get("result") and len(r["result"]) >= 66 else None


def list_nft(wallet, nft, token_id, price_bnb, days=30, send=False):
    me = WALLETS[wallet]; nft = nft.lower()
    if owner_of(nft, token_id) != me.lower(): return {"ok": False, "error": "wallet does not own this token"}
    fee_bps, fee_to, roy_bps, roy_to = collection_fees(nft, token_id)
    amount = int(round(float(price_bnb) * 1e18))
    if amount >= 1 << 96: return {"ok": False, "error": "price too large"}
    now = int(time.time()); listing, expiry = now - 60, now + int(days) * 86400
    res = {"nft": nft, "tokenId": str(token_id), "priceBNB": float(price_bnb), "platformFeeBps": fee_bps, "royaltyBps": roy_bps,
           "youGetBNB": amount * (10000 - fee_bps - roy_bps) / 10000 / 1e18, "approved": is_approved(me, nft)}
    if not send: return res
    if not res["approved"]:
        ap = baw_send(wallet, nft, sel("setApprovalForAll(address,bool)") + EX[2:].lower().zfill(64) + "1".zfill(64))
        res["approveTx"] = ap
        if not ap.get("ok"): return res
    start_nonce = int(api("/v3/orders/getMakerNonce", {"maker": me.lower(), "schema": "erc721", "count": 1, "exchange": EX.lower(), "chain": "bsc"}))
    try: oracle = int(api("/v1/orders/confData", {"chainId": "0x38", "chain": "bsc", "standard": "element-ex-v3"}, timeout=45).get("oracleSignature", 0))
    except Exception: oracle = 1
    hash_nonce = int(eth_call(ZERO, EX, sel("getHashNonce(address)") + me[2:].lower().zfill(64))["result"], 16)
    bc = {"nftAddress": nft, "platformFee": fee_bps, "royaltyFeeRecipient": roy_to, "royaltyFee": roy_bps,
          "items": [{"erc20TokenAmount": str(amount), "nftId": str(token_id)}]}
    msg = {"maker": me.lower(), "listingTime": listing, "expiryTime": int(bits([(0, 4), (oracle, 4), (expiry, 248)]), 16),
           "startNonce": start_nonce, "erc20Token": NATIVE, "platformFeeRecipient": fee_to,
           "basicCollections": [{"nftAddress": nft, "fee": bits([(0, 64), (fee_bps, 16), (roy_bps, 16), (roy_to, 160)]),
                                 "items": [bits([(amount, 96), (int(token_id), 160)])]}],
           "collections": [], "hashNonce": hash_nonce}
    typed = {"types": BS_TYPES, "primaryType": "BatchSignedERC721Orders",
             "domain": {"name": "ElementEx", "version": "1.0.0", "chainId": CHAIN_ID, "verifyingContract": EX.lower()}, "message": msg}
    v, r, s = baw_sign_typed(wallet, typed)
    order_hash = _typed_hash(typed)
    order = {"listingTime": listing, "expirationTime": expiry, "paymentToken": ZERO, "platformFeeRecipient": fee_to,
             "basicCollections": [bc], "collections": [], "chain": "bsc", "maker": me.lower(), "exchange": EX.lower(),
             "startNonce": start_nonce, "oracleSignature": oracle, "hashNonce": str(hash_nonce),
             "v": v, "r": r, "s": s, "signatureType": 0, "hash": order_hash}
    # sanity: the signature must recover to the maker. A fill simulation is not possible here because
    # oracleSignature=1 orders need Element's oracle extraData, which the server only adds at fill time.
    from eth_account import Account
    signer = Account._recover_hash(bytes.fromhex(order_hash[2:]), vrs=(v, int(r, 16), int(s, 16)))
    res["signer"] = signer
    if signer.lower() != me.lower():
        res["ok"] = False; res["error"] = "signature does not recover to maker; not posted"; return res
    posted = api("/v3/orders/postBatch", order)
    res.update({"ok": bool((posted or {}).get("successList")), "post": posted, "nonce": start_nonce})
    return res


def _typed_hash(typed):
    sm = encode_typed_data(full_message=typed)
    return "0x" + keccak(b"\x19\x01" + sm.header + sm.body).hex()


# ------------------------------------------------------------------ cancel
def cancel(wallet, nonce, send=False):
    data = sel("cancelERC721Order(uint256)") + format(int(nonce), "064x")
    sim = eth_call(WALLETS[wallet], EX, data)
    res = {"nonce": int(nonce), "simulate": "OK" if "result" in sim else sim.get("error", {}).get("message", "")[:160]}
    if send and "result" in sim: res.update(baw_send(wallet, EX, data))
    return res


# ------------------------------------------------------------------ cli
def main(a):
    send = "--send" in a; a = [x for x in a if x != "--send"]
    days = 30
    if "--days" in a: i = a.index("--days"); days = int(a[i + 1]); del a[i:i + 2]
    cmd = a[0] if a else "help"
    if cmd == "floor": out = floor(a[1], int(a[2]) if len(a) > 2 else 5)
    elif cmd == "item": out = item(a[1], a[2])
    elif cmd == "mine": out = mine(a[1])
    elif cmd == "buy": out = buy(a[1], a[2], send)
    elif cmd == "list": out = list_nft(a[1], a[2], a[3], a[4], days, send)
    elif cmd == "cancel": out = cancel(a[1], a[2], send)
    else: print(__doc__); return
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])

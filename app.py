# app.py
# Solfire - Ultra Professional Exchange Edition
# Requires: flask, requests
# Run: python app.py  -> open http://127.0.0.1:5000/login-page

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import os, secrets, threading, time, uuid, random
import requests
from functools import wraps

# ---------- CONFIG ----------
WALLET_ADDRESS = "TAMvBeCmd9VruNxPGjNamMR2wL9EMHNVnU"
NETWORK_LABEL = "TRX (TRC20)"

VS_CURRENCY = "usd"
FETCH_INTERVAL = 30         # Reduced API calls to avoid bans
CLIENT_POLL_MS = 1500       # Client polling (1.5 seconds for super fast updates)
TOP_N = 50                  

STARTING_USDT = 0.0         
# ----------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(24)

# --- HARDCODED ROBUST INITIAL MARKET ---
# This ensures the screen is NEVER empty, even if the API fails.
INITIAL_MARKET = {
    "BTC": {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "price": 68450.20, "change_24h": 2.5, "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png"},
    "ETH": {"id": "ethereum", "symbol": "ETH", "name": "Ethereum", "price": 3850.10, "change_24h": 1.2, "image": "https://assets.coingecko.com/coins/images/279/large/ethereum.png"},
    "SOL": {"id": "solana", "symbol": "SOL", "name": "Solana", "price": 175.40, "change_24h": 5.4, "image": "https://assets.coingecko.com/coins/images/4128/large/solana.png"},
    "BNB": {"id": "binancecoin", "symbol": "BNB", "name": "BNB", "price": 590.30, "change_24h": -0.5, "image": "https://assets.coingecko.com/coins/images/825/large/bnb-icon2_2x.png"},
    "XRP": {"id": "ripple", "symbol": "XRP", "name": "XRP", "price": 0.62, "change_24h": 0.8, "image": "https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png"},
    "DOGE": {"id": "dogecoin", "symbol": "DOGE", "name": "Dogecoin", "price": 0.15, "change_24h": 12.0, "image": "https://assets.coingecko.com/coins/images/5/large/dogecoin.png"},
    "ADA": {"id": "cardano", "symbol": "ADA", "name": "Cardano", "price": 0.55, "change_24h": -1.2, "image": "https://assets.coingecko.com/coins/images/975/large/cardano.png"},
    "AVAX": {"id": "avalanche-2", "symbol": "AVAX", "name": "Avalanche", "price": 45.20, "change_24h": 3.1, "image": "https://assets.coingecko.com/coins/images/12559/large/Avalanche_Circle_RedWhite_Trans.png"},
    "TRX": {"id": "tron", "symbol": "TRX", "name": "TRON", "price": 0.12, "change_24h": 0.1, "image": "https://assets.coingecko.com/coins/images/1094/large/tron-logo.png"},
    "LINK": {"id": "chainlink", "symbol": "LINK", "name": "Chainlink", "price": 18.90, "change_24h": 4.5, "image": "https://assets.coingecko.com/coins/images/877/large/chainlink-new-logo.png"},
    "DOT": {"id": "polkadot", "symbol": "DOT", "name": "Polkadot", "price": 8.50, "change_24h": -2.1, "image": "https://assets.coingecko.com/coins/images/12171/large/polkadot.png"},
    "MATIC": {"id": "matic-network", "symbol": "MATIC", "name": "Polygon", "price": 0.95, "change_24h": 1.4, "image": "https://assets.coingecko.com/coins/images/4713/large/matic-token-icon.png"},
    "LTC": {"id": "litecoin", "symbol": "LTC", "name": "Litecoin", "price": 85.30, "change_24h": 0.5, "image": "https://assets.coingecko.com/coins/images/2/large/litecoin.png"},
    "BCH": {"id": "bitcoin-cash", "symbol": "BCH", "name": "Bitcoin Cash", "price": 450.20, "change_24h": 6.7, "image": "https://assets.coingecko.com/coins/images/780/large/bitcoin-cash-circle.png"},
    "SHIB": {"id": "shiba-inu", "symbol": "SHIB", "name": "Shiba Inu", "price": 0.000025, "change_24h": 15.3, "image": "https://assets.coingecko.com/coins/images/11939/large/shiba.png"},
    "UNI": {"id": "uniswap", "symbol": "UNI", "name": "Uniswap", "price": 11.20, "change_24h": -3.4, "image": "https://assets.coingecko.com/coins/images/12504/large/uniswap-uni.png"},
    "ATOM": {"id": "cosmos", "symbol": "ATOM", "name": "Cosmos", "price": 12.40, "change_24h": 2.2, "image": "https://assets.coingecko.com/coins/images/1481/large/cosmos_hub.png"},
    "XLM": {"id": "stellar", "symbol": "XLM", "name": "Stellar", "price": 0.13, "change_24h": 1.1, "image": "https://assets.coingecko.com/coins/images/100/large/Stellar_symbol_black_RGB.png"},
    "NEAR": {"id": "near", "symbol": "NEAR", "name": "NEAR Protocol", "price": 7.10, "change_24h": 8.9, "image": "https://assets.coingecko.com/coins/images/10365/large/near.png"},
    "APT": {"id": "aptos", "symbol": "APT", "name": "Aptos", "price": 14.50, "change_24h": -1.5, "image": "https://assets.coingecko.com/coins/images/26455/large/aptos_round.png"},
    "ARB": {"id": "arbitrum", "symbol": "ARB", "name": "Arbitrum", "price": 1.65, "change_24h": 4.2, "image": "https://assets.coingecko.com/coins/images/16547/large/photo_2023-03-29_21.47.00.jpeg"},
    "OP": {"id": "optimism", "symbol": "OP", "name": "Optimism", "price": 3.80, "change_24h": 5.1, "image": "https://assets.coingecko.com/coins/images/25244/large/Optimism.png"},
    "INJ": {"id": "injective-protocol", "symbol": "INJ", "name": "Injective", "price": 38.20, "change_24h": 11.4, "image": "https://assets.coingecko.com/coins/images/12882/large/Secondary_Symbol.png"},
    "RNDR": {"id": "render-token", "symbol": "RNDR", "name": "Render", "price": 10.50, "change_24h": 7.8, "image": "https://assets.coingecko.com/coins/images/11636/large/rndr.png"},
    "FTM": {"id": "fantom", "symbol": "FTM", "name": "Fantom", "price": 0.95, "change_24h": -4.2, "image": "https://assets.coingecko.com/coins/images/4001/large/Fantom_round.png"},
    "TIA": {"id": "celestia", "symbol": "TIA", "name": "Celestia", "price": 15.20, "change_24h": 2.1, "image": "https://assets.coingecko.com/coins/images/31967/large/celestia-logo.png"},
    "SEI": {"id": "sei-network", "symbol": "SEI", "name": "Sei", "price": 0.85, "change_24h": 6.3, "image": "https://assets.coingecko.com/coins/images/28205/large/Sei_Logo_-_Transparent.png"},
    "SUI": {"id": "sui", "symbol": "SUI", "name": "Sui", "price": 1.70, "change_24h": -2.8, "image": "https://assets.coingecko.com/coins/images/26375/large/sui-ocean-square.png"},
    "PEPE": {"id": "pepe", "symbol": "PEPE", "name": "Pepe", "price": 0.000007, "change_24h": 25.4, "image": "https://assets.coingecko.com/coins/images/29850/large/pepe-token.jpeg"},
    "WIF": {"id": "dogwifcoin", "symbol": "WIF", "name": "dogwifhat", "price": 2.80, "change_24h": 40.5, "image": "https://assets.coingecko.com/coins/images/33566/large/dogwifhat.jpg"},
    
    # --- FAKE / CUSTOM COINS ---
    "SLFR": {"id": "solfire", "symbol": "SLFR", "name": "Solfire Token", "price": 1.45, "change_24h": 150.5, "image": "https://cryptologos.cc/logos/fire-token-fire-logo.png"},
    "MOON": {"id": "moon", "symbol": "MOON", "name": "Moon Coin", "price": 0.0045, "change_24h": 45.2, "image": "https://cryptologos.cc/logos/safemoon-safemoon-logo.png"},
    "GEMS": {"id": "gems", "symbol": "GEMS", "name": "Gems Network", "price": 0.08, "change_24h": -5.6, "image": "https://cryptologos.cc/logos/kucoin-token-kcs-logo.png"},
    "RICH": {"id": "rich", "symbol": "RICH", "name": "Rich Protocol", "price": 12.30, "change_24h": 80.1, "image": "https://cryptologos.cc/logos/pancakeswap-cake-logo.png"},
    "NINJA": {"id": "ninja", "symbol": "NINJA", "name": "Ninja Coin", "price": 5.50, "change_24h": 12.4, "image": "https://cryptologos.cc/logos/sushi-sushi-logo.png"},
}

# in-memory stores
market_cache = {"last_update": 0, "data": INITIAL_MARKET.copy(), "prev": {}}
users_store = {}   
global_orderbook = {"limit_orders": []}

# ---------- helpers ----------
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
        symbols = list(market_cache.get("data", {}).keys())
        for s in symbols:
            bal[s] = 0.0
        users_store[sid] = {"balances": bal, "orders": [], "trades": [], "transfers": []}
    return users_store[sid]

# ---------- dynamic fetch top N coins ----------
def fetch_prices_once():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": VS_CURRENCY,
        "order": "market_cap_desc",
        "per_page": TOP_N,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h"
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        arr = resp.json()
        new = INITIAL_MARKET.copy() # keep fake coins
        
        for item in arr:
            sym = (item.get("symbol") or "").upper()
            if sym in ["SLFR", "MOON", "GEMS", "RICH", "NINJA"]: continue # skip overriding fake coins
            name = item.get("name") or ""
            cid = item.get("id") or ""
            price = item.get("current_price")
            change24 = item.get("price_change_percentage_24h")
            image = item.get("image")
            if price is not None:
                new[sym] = {"id": cid, "symbol": sym, "name": name, "price": float(price), "change_24h": change24, "image": image}
        
        market_cache["prev"] = market_cache.get("data", {}).copy()
        market_cache["data"] = new
        market_cache["last_update"] = int(time.time())
    except Exception as e:
        # Fails silently and keeps using the highly realistic hardcoded + jittered data
        pass

# ---------- Live Simulation Engine (Micro Jitters) ----------
# This function creates the realistic "1-second" tick without hitting API limits
def micro_jitter_worker():
    while True:
        data = market_cache.get("data", {})
        for k, v in data.items():
            if v.get("price"):
                # Randomly move price by -0.15% to +0.15% for strong visual effect
                jitter = random.uniform(-0.0015, 0.0015)
                v["price"] = max(1e-8, v["price"] * (1 + jitter))
            
            if v.get("change_24h") is not None:
                # Randomly move the 24h change slightly
                c_jitter = random.uniform(-0.05, 0.05)
                v["change_24h"] = v["change_24h"] + c_jitter

        try_match_limits()
        time.sleep(1.5) # Update prices every 1.5 seconds locally

def background_api_worker():
    while True:
        try:
            fetch_prices_once()
        except:
            pass
        time.sleep(FETCH_INTERVAL)

bg_api = threading.Thread(target=background_api_worker, daemon=True)
bg_api.start()

bg_jitter = threading.Thread(target=micro_jitter_worker, daemon=True)
bg_jitter.start()

# ---------- order execution ----------
def execute_order(order, exec_price, is_limit=False):
    sid = order["session_id"]
    user = users_store.get(sid)
    if not user: return
    qty = float(order["quantity"])
    cost = qty * float(exec_price)
    side = order["side"]
    sym = order["symbol"]
    if side == "buy":
        if user["balances"]["USDT"] + 1e-9 < cost:
            order["status"] = "cancelled_insufficient_funds"
            user["orders"].append(order); return
        user["balances"]["USDT"] -= cost
        user["balances"][sym] = user["balances"].get(sym, 0.0) + qty
    else:
        if user["balances"].get(sym,0.0) + 1e-9 < qty:
            order["status"] = "cancelled_insufficient_balance"
            user["orders"].append(order); return
        user["balances"][sym] -= qty
        user["balances"]["USDT"] += cost
    rec = dict(order)
    rec["executed_price"] = float(exec_price)
    rec["status"] = "filled"
    rec["filled_at"] = int(time.time())
    user["orders"].append(rec)
    user["trades"].append({"id": str(uuid.uuid4()), "symbol": sym, "side": side, "price": float(exec_price), "quantity": qty, "timestamp": int(time.time()), "from_limit": bool(is_limit)})

def try_match_limits():
    data = market_cache.get("data", {})
    to_rm = []
    for order in list(global_orderbook["limit_orders"]):
        sym = order["symbol"]
        price_now = data.get(sym, {}).get("price")
        if price_now is None: continue
        if order["side"] == "buy" and price_now <= order["limit_price"]:
            execute_order(order, price_now, is_limit=True); to_rm.append(order)
        elif order["side"] == "sell" and price_now >= order["limit_price"]:
            execute_order(order, price_now, is_limit=True); to_rm.append(order)
    for o in to_rm:
        try: global_orderbook["limit_orders"].remove(o)
        except: pass

# ---------- routes ----------
@app.route("/login-page")
def login_page():
    err = request.args.get("error", "")
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Solfire Pro - Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>body{margin:0;height:100vh;font-family:'Inter',sans-serif;background:#0b0e11;display:flex;align-items:center;justify-content:center;color:#eaecef}
    .box{width:92%;max-width:400px;padding:32px;border-radius:16px;background:#181a20;box-shadow: 0 8px 24px rgba(0,0,0,0.5);}
    label{display:block;margin-top:16px;color:#848e9c;font-size:14px;font-weight:600}
    input{width:100%;padding:12px;border-radius:8px;border:1px solid #2b3139;background:#0b0e11;color:#eaecef;margin-top:8px;box-sizing:border-box;}
    input:focus{outline:none;border-color:#fcd535;}
    .btn{width:100%;padding:14px;border-radius:8px;background:#fcd535;border:none;color:#181a20;font-weight:800;font-size:16px;margin-top:24px;cursor:pointer;transition:0.2s}
    .btn:hover{background:#e0be2f;}
    .err{margin-top:10px;color:#f6465c;background:rgba(246,70,92,0.1);padding:10px;border-radius:8px;font-size:14px}
    </style></head><body><div class="box">
    <div style="font-weight:800;color:#fcd535;font-size:32px;text-align:center;margin-bottom:8px;">SOLFIRE</div>
    <div style="color:#848e9c;text-align:center;margin-bottom:24px;font-size:14px">Professional Crypto Exchange</div>
    {% if err %}<div class="err">{{ err }}</div>{% endif %}
    <form method="post" action="{{ url_for('do_login') }}">
      <label>Email Address</label><input name="email" placeholder="user@gmail.com" autocomplete="off"/>
      <label>Password</label><input name="password" type="password" placeholder="••••••••" autocomplete="off"/>
      <button class="btn" type="submit">Log In</button>
    </form></div></body></html>"""
    return render_template_string(html, err=err)

@app.route("/login", methods=["POST"])
def do_login():
    email = (request.form.get("email") or "").strip()
    pwd = (request.form.get("password") or "")
    if not email or not pwd:
        return redirect(url_for("login_page", error="Email and password required"))
    if not email.lower().endswith("@gmail.com"):
        return redirect(url_for("login_page", error="Use a valid @gmail.com account"))
    session["user"] = {"email": email, "name": email.split("@")[0]}
    ensure_user_store()
    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))

@app.route("/api/prices")
def api_prices():
    return jsonify({"last_update": market_cache.get("last_update",0), "data": market_cache.get("data", {})})

@app.route("/api/account")
@login_required
def api_account():
    store = ensure_user_store()
    return jsonify({"usdt": store["balances"].get("USDT", 0.0), "orders": store["orders"], "trades": store["trades"], "transfers": store["transfers"]})

@app.route("/api/place_order", methods=["POST"])
@login_required
def api_place_order():
    sid = current_session_id()
    store = ensure_user_store()
    payload = request.get_json() or request.form
    symbol = (payload.get("symbol") or "").upper()
    side = (payload.get("side") or "").lower()
    typ = (payload.get("type") or "").lower()
    try: qty = float(payload.get("quantity") or 0.0)
    except: return jsonify({"ok": False, "error": "invalid quantity"}), 400
    if symbol not in market_cache.get("data", {}): return jsonify({"ok": False, "error": "unknown symbol"}), 400
    if side not in ("buy","sell"): return jsonify({"ok": False, "error": "invalid side"}), 400
    if typ not in ("market","limit"): return jsonify({"ok": False, "error": "invalid type"}), 400
    if qty <= 0: return jsonify({"ok": False, "error": "quantity must be > 0"}), 400
    market = market_cache.get("data", {}).get(symbol, {})
    price_now = market.get("price")
    order = {"id": str(uuid.uuid4()), "session_id": sid, "symbol": symbol, "side": side, "type": typ, "quantity": qty, "created_at": int(time.time()), "status": "open"}
    if typ == "market":
        if price_now is None: return jsonify({"ok": False, "error": "market price unavailable"}), 400
        execute_order(order, price_now, is_limit=False)
        return jsonify({"ok": True, "executed_price": price_now})
    else:
        try: lim = float(payload.get("limit_price"))
        except: return jsonify({"ok": False, "error": "invalid limit_price"}), 400
        order["limit_price"] = lim
        if side == "buy":
            reserve = lim * qty
            if store["balances"]["USDT"] + 1e-9 < reserve: return jsonify({"ok": False, "error": "insufficient USDT"}), 400
            store["balances"]["USDT"] -= reserve
            order["reserved_usdt"] = reserve
        else:
            if store["balances"].get(symbol,0.0) + 1e-9 < qty: return jsonify({"ok": False, "error": f"insufficient {symbol}"}), 400
            store["balances"][symbol] -= qty
            order["reserved_qty"] = qty
        global_orderbook["limit_orders"].append(order)
        return jsonify({"ok": True, "placed": order})

@app.route("/api/withdraw", methods=["POST"])
@login_required
def api_withdraw():
    sid = current_session_id()
    store = ensure_user_store()
    payload = request.get_json() or request.form
    try: amt = float(payload.get("amount") or 0.0)
    except: return jsonify({"ok": False, "error": "invalid amount"}), 400
    addr = (payload.get("address") or "").strip()
    network = (payload.get("network") or NETWORK_LABEL).strip()
    if amt <= 0: return jsonify({"ok": False, "error": "amount must be > 0"}), 400
    if not addr: return jsonify({"ok": False, "error": "address required"}), 400
    if store["balances"].get("USDT", 0.0) + 1e-9 < amt: return jsonify({"ok": False, "error": "insufficient USDT"}), 400
    store["balances"]["USDT"] -= amt
    tx = {"id": str(uuid.uuid4()), "to": addr, "network": network, "amount": amt, "status": "Processing", "timestamp": int(time.time())}
    store["transfers"].append(tx)
    return jsonify({"ok": True, "tx": tx, "new_balance": store["balances"]["USDT"]})

@app.route("/")
@login_required
def home():
    user = session.get("user", {"name":"User","email":""})
    html = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=0">
<title>Solfire Pro - Exchange</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
:root{--bg:#0b0e11;--card:#181a20;--card-hover:#2b3139;--text:#eaecef;--muted:#848e9c;--accent:#fcd535;--green:#0ecb81;--red:#f6465c;--border:#2b3139;}
body{margin:0;font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);padding-bottom:70px;user-select:none; -webkit-tap-highlight-color: transparent;}
* {box-sizing: border-box;}

/* Utilities */
.text-green { color: var(--green) !important; }
.text-red { color: var(--red) !important; }
.bg-green { background: rgba(14,203,129,0.1); color: var(--green); }
.bg-red { background: rgba(246,70,92,0.1); color: var(--red); }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.text-muted { color: var(--muted); font-size: 13px; }
.font-bold { font-weight: 700; }

/* Navbar */
.navbar { padding: 16px; display: flex; justify-content: space-between; align-items: center; background: var(--bg); position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--border); }
.brand { font-weight: 800; color: var(--accent); font-size: 20px; display:flex; align-items:center; gap:8px;}
.nav-icons { display: flex; gap: 16px; font-size: 18px; color: var(--text); }
.nav-icons i { cursor:pointer; }

/* Hero Balance */
.hero { padding: 20px 16px; background: linear-gradient(180deg, var(--card) 0%, var(--bg) 100%); }
.balance-title { font-size: 14px; color: var(--muted); margin-bottom: 4px; display:flex; justify-content:space-between}
.balance-val { font-size: 32px; font-weight: 800; margin-bottom: 4px; display:flex; align-items:baseline; gap:6px;}
.pnl { font-size: 14px; margin-bottom: 16px; font-weight:600; }
.action-buttons { display: flex; gap: 10px; }
.btn-action { flex: 1; background: var(--card-hover); border: none; padding: 12px 0; border-radius: 8px; color: var(--text); font-weight: 600; cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: 13px; transition: 0.2s;}
.btn-action i { font-size: 18px; }
.btn-action.primary { background: var(--accent); color: var(--bg); }
.btn-action:active { transform: scale(0.96); }

/* Quick Actions Grid */
.quick-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; padding: 0 16px 16px; text-align: center; font-size: 12px; font-weight: 500;}
.q-item { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--muted); cursor:pointer;}
.q-icon { width: 40px; height: 40px; background: var(--card); border-radius: 12px; display: flex; justify-content: center; align-items: center; font-size: 18px; color: var(--accent); transition:0.2s;}
.q-item:active .q-icon { background: var(--card-hover); }

/* Markets List */
.markets-container { padding: 0 16px; }
.tabs { display: flex; gap: 20px; border-bottom: 1px solid var(--border); margin-bottom: 12px; overflow-x: auto; white-space: nowrap;}
.tab { padding-bottom: 10px; color: var(--muted); font-weight: 600; cursor: pointer; font-size: 14px; transition:0.2s;}
.tab.active { color: var(--text); border-bottom: 2px solid var(--accent); }

.search-box { display: flex; align-items: center; background: var(--card); border-radius: 8px; padding: 8px 12px; margin-bottom: 16px; }
.search-box input { background: transparent; border: none; color: var(--text); width: 100%; outline: none; margin-left: 8px; font-family:'Inter'; font-size:14px; }

.market-header { display: grid; grid-template-columns: 2fr 1fr 1fr; padding: 8px 0; font-size: 12px; color: var(--muted); font-weight:600;}
.market-header div:nth-child(2) { text-align: right; }
.market-header div:nth-child(3) { text-align: right; }

.coin-row { display: grid; grid-template-columns: 2fr 1fr 1fr; padding: 14px 0; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.03); cursor: pointer; transition: background 0.2s; }
.coin-row:active { background: var(--card); }
.coin-info { display: flex; align-items: center; gap: 12px; }
.coin-img { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; background:#fff;}
.price-col { text-align: right; font-weight: 600; font-size: 15px; transition: color 0.3s ease; }
.change-btn { justify-self: end; padding: 6px 10px; border-radius: 4px; font-size: 13px; font-weight: 600; width: 75px; text-align: center; }

/* Flashing animations for real-time vibe */
@keyframes flashGreen { 0% { color: var(--green); } 100% { color: var(--text); } }
@keyframes flashRed { 0% { color: var(--red); } 100% { color: var(--text); } }
.flash-up { animation: flashGreen 0.8s ease-out; }
.flash-down { animation: flashRed 0.8s ease-out; }

/* Bottom Nav */
.bottom-nav { position: fixed; bottom: 0; width: 100%; background: var(--card); display: flex; justify-content: space-around; padding: 12px 0; border-top: 1px solid var(--border); z-index: 50; }
.nav-item { display: flex; flex-direction: column; align-items: center; gap: 4px; color: var(--muted); font-size: 11px; cursor: pointer; transition:0.2s; }
.nav-item.active { color: var(--accent); font-weight:600;}
.nav-item i { font-size: 20px; }

/* Modals */
.modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 100; display: none; justify-content: center; align-items: flex-end; backdrop-filter: blur(2px); }
.modal-overlay.show { display: flex; }
.modal-content { background: var(--card); width: 100%; max-width: 500px; border-radius: 20px 20px 0 0; padding: 24px; animation: slideUp 0.3s ease-out; max-height: 90vh; overflow-y:auto;}
@keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }

.m-title { font-size: 18px; font-weight: 700; margin-bottom: 20px; display: flex; justify-content: space-between; }
.m-title i { color: var(--muted); cursor: pointer; font-size:20px;}

/* Trade UI specific */
.trade-tabs { display:flex; gap:10px; margin-bottom:16px;}
.trade-btn { flex:1; padding:10px; text-align:center; border-radius:8px; font-weight:700; cursor:pointer; background:var(--bg); border:1px solid var(--border);}
.trade-btn.buy.selected { background:var(--green); color:#fff; border-color:var(--green);}
.trade-btn.sell.selected { background:var(--red); color:#fff; border-color:var(--red);}

.input-group { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; display: flex; align-items: center; padding: 0 12px; margin-bottom: 16px; }
.input-group input { flex: 1; border: none; background: transparent; padding: 14px 0; color: var(--text); font-size: 16px; font-weight: 600; outline:none;}
.input-label { color: var(--muted); font-size: 14px; margin-right: 8px; width:50px;}
.input-suffix { color: var(--text); font-weight: 600; font-size:14px;}

.action-btn-large { width: 100%; padding: 16px; border-radius: 8px; font-weight: 700; font-size: 16px; border: none; cursor: pointer; margin-top: 10px; color:#fff;}

/* Mini orderbook */
.mini-ob { font-family: monospace; font-size:12px; margin-bottom:16px;}
.ob-row { display:flex; justify-content:space-between; margin-bottom:4px;}

/* Toast Notification */
#toast {
    position: fixed; top: 80px; left: 50%; transform: translateX(-50%);
    background: var(--card-hover); color: var(--text); padding: 12px 24px;
    border-radius: 30px; font-size: 14px; font-weight: 600; z-index: 999;
    display: none; border: 1px solid var(--border);
    box-shadow: 0 8px 16px rgba(0,0,0,0.5);
    animation: fadeInOut 2.5s ease-in-out forwards;
}
@keyframes fadeInOut {
    0% { opacity: 0; transform: translate(-50%, -20px); }
    15% { opacity: 1; transform: translate(-50%, 0); }
    85% { opacity: 1; transform: translate(-50%, 0); }
    100% { opacity: 0; transform: translate(-50%, -20px); }
}
</style>
</head><body>

  <div id="toast">Message</div>

  <div class="navbar">
    <div class="brand"><i class="fa-solid fa-fire"></i> SOLFIRE</div>
    <div class="nav-icons">
      <i class="fa-solid fa-magnifying-glass" onclick="showToast('Opening Search...')"></i>
      <i class="fa-solid fa-qrcode" onclick="showToast('QR Scanner Starting...')"></i>
      <i class="fa-regular fa-bell" onclick="showToast('No new notifications')"></i>
    </div>
  </div>

  <div class="hero">
    <div class="balance-title"><span>Total Balance</span> <i class="fa-regular fa-eye" onclick="showToast('Balance visibility toggled')"></i></div>
    <div class="balance-val"><span id="usdtBalance">0.00</span> <span style="font-size:16px;font-weight:600">USDT</span></div>
    <div class="pnl text-green" id="dailyPnl">+0.00 (0.00%) Today</div>
    
    <div class="action-buttons">
      <button class="btn-action primary" onclick="openDepositModal()"><i class="fa-solid fa-wallet"></i> Deposit</button>
      <button class="btn-action" onclick="openSendModal()"><i class="fa-solid fa-paper-plane"></i> Withdraw</button>
      <button class="btn-action" onclick="openTransferModal()"><i class="fa-solid fa-right-left"></i> Transfer</button>
    </div>
  </div>

  <div class="quick-grid">
    <div class="q-item" onclick="showToast('P2P Trading is loading...')"><div class="q-icon"><i class="fa-solid fa-users"></i></div>P2P Trading</div>
    <div class="q-item" onclick="showToast('Buy Crypto gateway opening...')"><div class="q-icon"><i class="fa-solid fa-credit-card"></i></div>Buy Crypto</div>
    <div class="q-item" onclick="showToast('Earn: Staking currently locked')"><div class="q-icon"><i class="fa-solid fa-piggy-bank"></i></div>Earn</div>
    <div class="q-item" onclick="showToast('More features coming soon!')"><div class="q-icon" style="color:var(--text)"><i class="fa-solid fa-ellipsis"></i></div>More</div>
  </div>

  <div style="height:8px; background:var(--card);"></div> 
  <div class="markets-container" style="padding-top:16px;">
    <div class="tabs">
      <div class="tab" onclick="switchTab(this, 'Favorites')"><i class="fa-solid fa-star" style="font-size:12px;"></i> Favorites</div>
      <div class="tab active" onclick="switchTab(this, 'Hot')">Hot</div>
      <div class="tab" onclick="switchTab(this, 'Gainers')">Gainers</div>
      <div class="tab" onclick="switchTab(this, 'Losers')">Losers</div>
      <div class="tab" onclick="switchTab(this, 'New Listing')">New Listing</div>
    </div>

    <div class="search-box">
      <i class="fa-solid fa-search text-muted"></i>
      <input type="text" id="searchInput" placeholder="Search Coin Pairs">
    </div>

    <div class="market-header">
      <div>Name / Vol</div>
      <div>Last Price</div>
      <div>24h Chg%</div>
    </div>

    <div id="marketsList">
      </div>
  </div>

  <div class="bottom-nav">
    <div class="nav-item active" onclick="switchNav(this, 'Home')"><i class="fa-solid fa-house"></i> Home</div>
    <div class="nav-item" onclick="switchNav(this, 'Markets')"><i class="fa-solid fa-chart-simple"></i> Markets</div>
    <div class="nav-item" onclick="switchNav(this, 'Trade', true)"><i class="fa-solid fa-money-bill-transfer"></i> Trade</div>
    <div class="nav-item" onclick="switchNav(this, 'Futures')"><i class="fa-solid fa-bolt"></i> Futures</div>
    <div class="nav-item" onclick="switchNav(this, 'Wallets')"><i class="fa-solid fa-wallet"></i> Wallets</div>
  </div>

  <div id="depositModal" class="modal-overlay">
    <div class="modal-content">
      <div class="m-title"><span>Deposit Crypto</span> <i class="fa-solid fa-xmark" onclick="closeModal('depositModal')"></i></div>
      
      <div style="background:var(--bg); padding:20px; border-radius:12px; margin-bottom:16px;">
          <div class="text-muted" style="margin-bottom:12px; font-weight:600; font-size:14px;">your wallet address :</div>
          <div style="display:flex; justify-content:space-between; align-items:center; background:var(--card); padding:16px; border-radius:8px; border:1px solid var(--border);">
              <span id="depAddress" style="font-family:monospace; font-size:14px; word-break:break-all; color:var(--text); font-weight:700;">TAMvBeCmd9VruNxPGjNamMR2wL9EMHNVnU</span>
              <div onclick="copyDepAddress()" style="background:rgba(252, 213, 53, 0.1); padding:10px; border-radius:8px; cursor:pointer; margin-left:16px; transition:0.2s;">
                  <i class="fa-regular fa-copy" style="color:var(--accent); font-size:20px;"></i>
              </div>
          </div>
          <div class="text-muted" style="margin-top:20px; font-weight:600; font-size:14px;">The network : TRX ( TRC20 )</div>
      </div>
      <div id="copyMsg" class="text-green" style="text-align:center; font-size:14px; font-weight:700; height:20px;"></div>
    </div>
  </div>

  <div id="transferModal" class="modal-overlay">
    <div class="modal-content">
      <div class="m-title"><span>Transfer</span> <i class="fa-solid fa-xmark" onclick="closeModal('transferModal')"></i></div>
      <div class="input-group" style="padding:14px; margin-bottom:8px; background:var(--card-hover);">
          <div class="text-muted" style="width:50px;">From</div>
          <div style="font-weight:700;">Spot Wallet</div>
      </div>
      <div style="text-align:center; color:var(--accent); margin-bottom:8px;"><i class="fa-solid fa-arrow-down"></i></div>
      <div class="input-group" style="padding:14px; background:var(--card-hover);">
          <div class="text-muted" style="width:50px;">To</div>
          <div style="font-weight:700;">Futures Wallet</div>
      </div>
      
      <div class="input-group" style="margin-top:20px;">
        <div class="input-label" style="width:60px;">Coin</div>
        <input type="text" value="USDT" readonly style="font-weight:700;">
      </div>

      <div class="input-group">
        <div class="input-label" style="width:60px;">Amount</div>
        <input id="transferAmount" type="number" placeholder="Please enter amount">
        <div class="input-suffix text-accent" style="color:var(--accent); cursor:pointer;" onclick="document.getElementById('transferAmount').value=userUsdt.toFixed(2)">MAX</div>
      </div>
      <button class="action-btn-large primary" style="background:var(--accent); color:var(--bg);" onclick="doTransfer()">Confirm Transfer</button>
    </div>
  </div>

  <div id="sendModal" class="modal-overlay">
    <div class="modal-content">
      <div class="m-title"><span>Withdraw USDT</span> <i class="fa-solid fa-xmark" onclick="closeModal('sendModal')"></i></div>
      
      <div class="input-group">
        <div class="input-label" style="width:60px;">Address</div>
        <input id="sendAddress" type="text" placeholder="Long press to paste">
        <i class="fa-solid fa-paste text-muted" onclick="showToast('Please allow clipboard access')"></i>
      </div>

      <div class="input-group" style="padding:0">
        <select id="sendNetwork" style="width:100%; background:transparent; border:none; color:var(--text); padding:14px; outline:none; font-family:'Inter';font-weight:600;">
          <option>Tron (TRC20)</option>
          <option>Ethereum (ERC20)</option>
          <option>BNB Smart Chain (BEP20)</option>
        </select>
      </div>

      <div class="input-group">
        <div class="input-label" style="width:60px;">Amount</div>
        <input id="sendAmount" type="number" step="any" placeholder="Min 10">
        <div class="input-suffix text-accent" style="color:var(--accent); cursor:pointer;" onclick="document.getElementById('sendAmount').value=userUsdt.toFixed(2)">MAX</div>
      </div>

      <div style="display:flex; justify-content:space-between; margin-bottom:24px; font-size:13px;">
        <span class="text-muted">Available:</span>
        <span id="sendAvailable" class="font-bold">0.00 USDT</span>
      </div>

      <button class="action-btn-large primary" style="background:var(--accent); color:var(--bg);" onclick="doSend()">Withdraw</button>
      <div id="sendMsg" style="text-align:center; margin-top:10px; font-size:13px; font-weight:600;"></div>
    </div>
  </div>

  <div id="tradeModal" class="modal-overlay">
    <div class="modal-content">
      <div class="m-title"><span id="tradeTitle">BTC / USDT</span> <i class="fa-solid fa-xmark" onclick="closeModal('tradeModal')"></i></div>
      
      <div style="display:flex; gap:20px;">
        <div style="flex:1;">
          <div class="trade-tabs">
            <div id="btnBuy" class="trade-btn buy selected" onclick="setTradeSide('buy')">Buy</div>
            <div id="btnSell" class="trade-btn sell" onclick="setTradeSide('sell')">Sell</div>
          </div>

          <div class="input-group" style="padding:0">
            <select id="tradeType" style="width:100%; background:transparent; border:none; color:var(--text); padding:14px; outline:none; font-family:'Inter';font-weight:600;">
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </select>
          </div>

          <div class="input-group" id="limitBox" style="display:none;">
            <div class="input-label">Price</div>
            <input id="tradeLimit" type="number" step="any">
            <div class="input-suffix">USDT</div>
          </div>

          <div class="input-group">
            <div class="input-label">Qty</div>
            <input id="tradeQty" type="number" step="any" value="0.01">
            <div id="tradeCoinSuffix" class="input-suffix">BTC</div>
          </div>

          <div style="display:flex; justify-content:space-between; margin-bottom:16px; font-size:13px;">
            <span class="text-muted">Avail:</span>
            <span id="availBalance" class="font-bold">0.00 USDT</span>
          </div>

          <button id="submitTradeBtn" class="action-btn-large" style="background:var(--green);" onclick="submitTrade()">Buy BTC</button>
          <div id="tradeMsg" style="text-align:center; margin-top:10px; font-size:13px; font-weight:600;"></div>
        </div>

        <div style="width:110px;">
          <div class="mini-ob">
            <div class="ob-row text-red"><span><span id="obS3">0</span></span><span>1.2</span></div>
            <div class="ob-row text-red"><span><span id="obS2">0</span></span><span>0.8</span></div>
            <div class="ob-row text-red"><span><span id="obS1">0</span></span><span>2.4</span></div>
            <div style="margin:8px 0; font-size:16px; font-weight:800; text-align:center;" id="tradePriceMid" class="text-green">0.00</div>
            <div class="ob-row text-green"><span><span id="obB1">0</span></span><span>1.5</span></div>
            <div class="ob-row text-green"><span><span id="obB2">0</span></span><span>3.1</span></div>
            <div class="ob-row text-green"><span><span id="obB3">0</span></span><span>0.5</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>

<script>
const clientPoll = {{ client_poll }};
let marketData = {};
let marketKeys = [];
let prevPrices = {};
let currentSymbol = null;
let currentSide = 'buy';
let userUsdt = 0;

// Universal Toast Function
function showToast(msg) {
    const t = document.getElementById('toast');
    t.innerText = msg;
    t.style.display = 'block';
    t.style.animation = 'none';
    t.offsetHeight; // trigger reflow
    t.style.animation = 'fadeInOut 2.5s ease-in-out forwards';
    setTimeout(() => { t.style.display = 'none'; }, 2500);
}

// Deposit Logic
function openDepositModal() { document.getElementById('depositModal').classList.add('show'); }
function copyDepAddress() {
    navigator.clipboard.writeText("TAMvBeCmd9VruNxPGjNamMR2wL9EMHNVnU");
    const msg = document.getElementById('copyMsg');
    msg.innerText = "Address Copied Successfuly!";
    setTimeout(() => { msg.innerText = ""; }, 2500);
}

// Transfer Logic
function openTransferModal() { 
    document.getElementById('transferAmount').value = '';
    document.getElementById('transferModal').classList.add('show'); 
}
function doTransfer() {
    const amt = parseFloat(document.getElementById('transferAmount').value);
    if(!amt || amt <= 0) { showToast('Enter a valid amount!'); return; }
    if(amt > userUsdt) { showToast('Insufficient USDT Balance!'); return; }
    showToast('Transferring ' + amt + ' USDT to Futures...');
    setTimeout(()=>{ closeModal('transferModal'); showToast('Transfer Successful!'); }, 1000);
}

// UI Switchers
function switchTab(el, tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    showToast('Loading ' + tabName + ' pairs...');
}

function switchNav(el, navName, isTrade=false) {
    document.querySelectorAll('.nav-item').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    if(isTrade) { openTrade('BTC'); }
    else { showToast('Navigating to ' + navName + '...'); }
}

// Format numbers like real exchanges
function fmtPrice(p){ 
    if(p < 0.001) return p.toFixed(6);
    if(p < 1) return p.toFixed(4);
    if(p < 10) return p.toFixed(3);
    return p.toFixed(2);
}

function commaNum(x) { return x.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ","); }

async function fetchPrices(){
  try{
    const res = await fetch('/api/prices');
    const j = await res.json();
    marketData = j.data || {};
    marketKeys = Object.keys(marketData || {});
    renderMarketsLive(); // Improved rendering to stop flickering
    if(currentSymbol && document.getElementById('tradeModal').classList.contains('show')) {
        updateTradeModalLive();
    }
  }catch(e){}
}

async function fetchAccount(){
  try{
    const res = await fetch('/api/account');
    const j = await res.json();
    userUsdt = j.usdt || 0;
    
    // Fake PNL generation just for UI vibes
    let pnlVal = (userUsdt * 0.015).toFixed(2);
    document.getElementById('dailyPnl').innerText = `+${pnlVal} (1.50%) Today`;

    document.getElementById('usdtBalance').innerText = commaNum(userUsdt.toFixed(2));
    document.getElementById('sendAvailable').innerText = commaNum(userUsdt.toFixed(2)) + ' USDT';
    if(currentSide === 'buy') document.getElementById('availBalance').innerText = commaNum(userUsdt.toFixed(2)) + ' USDT';
  }catch(e){}
}

function renderMarketsLive(){
  const container = document.getElementById('marketsList');
  const q = (document.getElementById('searchInput').value || '').trim().toLowerCase();
  
  marketKeys.forEach(k => {
    const it = marketData[k] || {};
    const sym = it.symbol || k;
    const name = (it.name || '');
    const price = it.price ? Number(it.price) : 0;
    const change = it.change_24h ? Number(it.change_24h) : 0;
    const img = it.image || '';
    
    // Filtering
    let el = document.getElementById('row-'+k);
    if(q && !k.toLowerCase().includes(q) && !name.toLowerCase().includes(q)) {
        if(el) el.style.display = 'none';
        return;
    }
    
    // Create row if not exists (Prevents DOM destruction and flickering)
    if(!el) {
        el = document.createElement('div');
        el.id = 'row-'+k;
        el.className = 'coin-row';
        el.onclick = () => openTrade(k);
        el.innerHTML = `
          <div class="coin-info">
            <img class="coin-img" src="${img}" alt="${sym}" onerror="this.src='https://cryptologos.cc/logos/tether-usdt-logo.png'">
            <div>
              <div style="font-weight:700; font-size:15px; display:flex; gap:6px; align-items:center;">
                  ${sym} ${sym==='SLFR'?'<i class="fa-solid fa-fire text-accent" style="font-size:10px;"></i>':''}
              </div>
              <div class="text-muted" id="vol-${k}">Vol --</div>
            </div>
          </div>
          <div class="price-col" id="price-${k}">--</div>
          <div style="text-align:right;">
            <div class="change-btn" id="chg-${k}">--</div>
          </div>
        `;
        container.appendChild(el);
    }
    el.style.display = 'grid';

    // Update specific nodes cleanly
    document.getElementById('vol-'+k).innerText = `Vol ${(price * 1250).toFixed(0).slice(0,4)}M`;
    
    const priceEl = document.getElementById('price-'+k);
    const formattedPrice = fmtPrice(price);
    
    if(prevPrices[k] && price !== prevPrices[k]) {
        priceEl.classList.remove('flash-up', 'flash-down');
        void priceEl.offsetWidth; // Force CSS reflow
        priceEl.classList.add(price > prevPrices[k] ? 'flash-up' : 'flash-down');
    }
    priceEl.innerText = formattedPrice;
    prevPrices[k] = price;

    const chgEl = document.getElementById('chg-'+k);
    chgEl.className = 'change-btn ' + (change < 0 ? 'bg-red' : 'bg-green');
    chgEl.innerText = (change > 0 ? '+' : '') + change.toFixed(2) + '%';
  });
}

function openTrade(sym){
  currentSymbol = sym;
  document.getElementById('tradeTitle').innerText = sym + ' / USDT';
  document.getElementById('tradeCoinSuffix').innerText = sym;
  document.getElementById('tradeMsg').innerText = '';
  document.getElementById('tradeMsg').className = '';
  
  setTradeSide('buy');
  updateTradeModalLive();
  document.getElementById('tradeModal').classList.add('show');
}

function updateTradeModalLive() {
    if(!currentSymbol) return;
    const it = marketData[currentSymbol] || {};
    const p = it.price ? Number(it.price) : 0;
    
    document.getElementById('tradePriceMid').innerText = fmtPrice(p);
    if(document.getElementById('tradeLimit').value === '' || document.getElementById('tradeType').value === 'market'){
        document.getElementById('tradeLimit').value = fmtPrice(p);
    }

    // Fake Orderbook generation around current price
    const spread = p * 0.0008;
    document.getElementById('obS3').innerText = fmtPrice(p + spread*3);
    document.getElementById('obS2').innerText = fmtPrice(p + spread*2);
    document.getElementById('obS1').innerText = fmtPrice(p + spread*1);
    
    document.getElementById('obB1').innerText = fmtPrice(p - spread*1);
    document.getElementById('obB2').innerText = fmtPrice(p - spread*2);
    document.getElementById('obB3').innerText = fmtPrice(p - spread*3);
}

function setTradeSide(side) {
    currentSide = side;
    document.getElementById('btnBuy').classList.remove('selected');
    document.getElementById('btnSell').classList.remove('selected');
    const btn = document.getElementById('submitTradeBtn');
    
    if(side === 'buy') {
        document.getElementById('btnBuy').classList.add('selected');
        btn.innerText = 'Buy ' + currentSymbol;
        btn.style.background = 'var(--green)';
        document.getElementById('availBalance').innerText = commaNum(userUsdt.toFixed(2)) + ' USDT';
    } else {
        document.getElementById('btnSell').classList.add('selected');
        btn.innerText = 'Sell ' + currentSymbol;
        btn.style.background = 'var(--red)';
        document.getElementById('availBalance').innerText = '-- ' + currentSymbol;
    }
}

document.getElementById('tradeType').addEventListener('change', (e) => {
    document.getElementById('limitBox').style.display = e.target.value === 'limit' ? 'flex' : 'none';
});

async function submitTrade(){
  const type = document.getElementById('tradeType').value;
  const qty = parseFloat(document.getElementById('tradeQty').value)||0;
  const limit = parseFloat(document.getElementById('tradeLimit').value)||undefined;
  const msgBox = document.getElementById('tradeMsg');
  
  if(qty <= 0){ msgBox.innerText='Enter valid quantity'; msgBox.className='text-red'; return; }
  
  btnLoad('submitTradeBtn', true);
  const body = { symbol: currentSymbol, side: currentSide, type: type, quantity: qty };
  if(type === 'limit') body.limit_price = limit;
  
  try {
      const res = await fetch('/api/place_order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const j = await res.json();
      if(j.ok){
        msgBox.innerText = 'Order Placed Successfully!';
        msgBox.className = 'text-green';
        fetchAccount();
      } else {
        msgBox.innerText = j.error || 'Error';
        msgBox.className = 'text-red';
      }
  } catch(e) {
      msgBox.innerText = 'Network error';
      msgBox.className = 'text-red';
  }
  btnLoad('submitTradeBtn', false, currentSide === 'buy' ? 'Buy '+currentSymbol : 'Sell '+currentSymbol);
}

function openSendModal(){
  document.getElementById('sendAmount').value = '';
  document.getElementById('sendAddress').value = '';
  document.getElementById('sendMsg').innerText = '';
  document.getElementById('sendModal').classList.add('show');
}

function closeModal(id){ document.getElementById(id).classList.remove('show'); }

async function doSend(){
  const amount = parseFloat(document.getElementById('sendAmount').value) || 0;
  const address = document.getElementById('sendAddress').value.trim();
  const network = document.getElementById('sendNetwork').value;
  const msgBox = document.getElementById('sendMsg');
  
  if(amount <= 0){ msgBox.innerText = 'Enter valid amount'; msgBox.className='text-red'; return; }
  if(!address){ msgBox.innerText = 'Enter address'; msgBox.className='text-red'; return; }
  
  const res = await fetch('/api/withdraw', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({amount: amount, address: address, network: network})});
  const j = await res.json();
  if(j.ok){
    msgBox.innerText = 'Withdrawal Processing...';
    msgBox.className = 'text-green';
    fetchAccount();
    setTimeout(()=> closeModal('sendModal'), 1500);
  } else {
    msgBox.innerText = j.error || 'Error';
    msgBox.className = 'text-red';
  }
}

function btnLoad(id, isLoading, originalText = '') {
    const b = document.getElementById(id);
    if(isLoading) { b.disabled = true; b.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>'; }
    else { b.disabled = false; b.innerText = originalText; }
}

// Search filtering trigger
document.getElementById('searchInput').addEventListener('input', renderMarketsLive);

// Initialization & Loops
fetchAccount();
fetchPrices();
setInterval(fetchPrices, clientPoll); // Frontend polling every 1.5s
</script>
</body></html>
"""
    return render_template_string(html, user=user, wallet=WALLET_ADDRESS, network=NETWORK_LABEL, client_poll=CLIENT_POLL_MS)

# ---------- run ----------
if __name__ == "__main__":
    fetch_prices_once()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

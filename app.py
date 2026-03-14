# app.py
# Solfire - vertical layout with search + dynamic top N coins, Send (withdraw) USDT feature
# TopUp removed, USDT-only balance on top
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
FETCH_INTERVAL = 10         # backend fetch seconds (CoinGecko)
CLIENT_POLL_MS = 3000       # client polling ms
TOP_N = 150                 # fetch top 150 coins (>= 100 as requested)

STARTING_USDT = 0.0         # start with zero USDT as requested
# ----------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(24)

# in-memory stores
# market_cache.data: dict symbol_upper -> {id, symbol, name, price, change_24h, image}
market_cache = {"last_update": 0, "data": {}, "prev": {}}
users_store = {}   # sid -> {balances, orders, trades, transfers}
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
        # Build token list from market_cache if available, else fallback list
        bal = {"USDT": float(STARTING_USDT)}
        symbols = list(market_cache.get("data", {}).keys())
        if not symbols:
            symbols = ["BTC","ETH","SOL","BNB","TRX","DOGE","SHIBA"]
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
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
        arr = resp.json()
        new = {}
        symbol_counts = {}
        prev = market_cache.get("data", {})
        for item in arr:
            sym = (item.get("symbol") or "").upper()
            name = item.get("name") or ""
            cid = item.get("id") or ""
            price = item.get("current_price")
            change24 = item.get("price_change_percentage_24h")
            image = item.get("image")
            # handle duplicate symbols
            count = symbol_counts.get(sym, 0)
            symbol_counts[sym] = count + 1
            key = sym if count == 0 else f"{sym}-{count+1}"
            new[key] = {"id": cid, "symbol": sym, "name": name, "price": float(price) if price is not None else None, "change_24h": change24, "image": image}
        # jitter if API returns identical prices or missing
        for k, v in list(new.items()):
            p = v.get("price")
            prevp = prev.get(k, {}).get("price")
            if p is None and prevp is not None:
                jitter = random.uniform(-0.003, 0.003)
                new[k]["price"] = max(1e-8, prevp * (1 + jitter))
            elif p is not None and prevp is not None and abs(p - prevp) < 1e-9:
                jitter = random.uniform(-0.0015, 0.0015)
                new[k]["price"] = max(1e-8, p * (1 + jitter))
        market_cache["prev"] = market_cache.get("data", {}).copy()
        market_cache["data"] = new
        market_cache["last_update"] = int(time.time())
    except Exception as e:
        prev = market_cache.get("data", {})
        if prev:
            jittered = {}
            for k, item in prev.items():
                p = item.get("price")
                if p:
                    j = random.uniform(-0.003, 0.003)
                    jittered[k] = {**item, "price": max(1e-8, p * (1 + j))}
                else:
                    jittered[k] = item
            market_cache["prev"] = market_cache.get("data", {}).copy()
            market_cache["data"] = jittered
            market_cache["last_update"] = int(time.time())
        else:
            print("fetch_prices_once error (no prev):", e)

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

# background updater
def background_worker():
    while True:
        try:
            fetch_prices_once()
            try_match_limits()
        except Exception as e:
            print("bg error:", e)
        time.sleep(FETCH_INTERVAL)

bg = threading.Thread(target=background_worker, daemon=True)
bg.start()

# ---------- routes ----------
@app.route("/login-page")
def login_page():
    err = request.args.get("error", "")
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>solfire — Sign In</title>
    <style>body{margin:0;height:100vh;font-family:Inter,Arial;background:linear-gradient(180deg,#071033,#020617);display:flex;align-items:center;justify-content:center;color:#e6eef8}
    .box{width:92%;max-width:480px;padding:28px;border-radius:12px;background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01))}
    label{display:block;margin-top:12px;color:#94a3b8}
    input{width:100%;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.04);background:rgba(255,255,255,0.02);color:#e6eef8;margin-top:8px}
    .btn{width:100%;padding:12px;border-radius:10px;background:linear-gradient(90deg,#ffb703,#ff7b54);border:none;color:#071033;font-weight:800;margin-top:12px}
    .err{margin-top:10px;color:#ffb4b4;background:rgba(255,71,71,0.06);padding:8px;border-radius:8px}
    </style></head><body><div class="box">
    <div style="font-weight:900;color:#ffb703;font-size:28px">solfire</div>
    <div class="small" style="color:#94a3b8;margin-top:6px">Sign in with Gmail</div>
    {% if err %}<div class="err">{{ err }}</div>{% endif %}
    <form method="post" action="{{ url_for('do_login') }}">
      <label>Email</label><input name="email" placeholder="you@gmail.com" autocomplete="off"/>
      <label>Password</label><input name="password" type="password" placeholder="password" autocomplete="off"/>
      <button class="btn" type="submit">Sign in</button>
    </form></div></body></html>"""
    return render_template_string(html, err=err)

@app.route("/login", methods=["POST"])
def do_login():
    email = (request.form.get("email") or "").strip()
    pwd = (request.form.get("password") or "")
    if not email or not pwd:
        return redirect(url_for("login_page", error="Email and password required"))
    if not email.lower().endswith("@gmail.com"):
        return redirect(url_for("login_page", error="Email must end with @gmail.com"))
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
    try:
        qty = float(payload.get("quantity") or 0.0)
    except:
        return jsonify({"ok": False, "error": "invalid quantity"}), 400
    if symbol not in market_cache.get("data", {}):
        return jsonify({"ok": False, "error": "unknown symbol"}), 400
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
        try:
            lim = float(payload.get("limit_price"))
        except:
            return jsonify({"ok": False, "error": "invalid limit_price"}), 400
        order["limit_price"] = lim
        if side == "buy":
            reserve = lim * qty
            if store["balances"]["USDT"] + 1e-9 < reserve:
                return jsonify({"ok": False, "error": "insufficient USDT to place buy limit"}), 400
            store["balances"]["USDT"] -= reserve
            order["reserved_usdt"] = reserve
        else:
            if store["balances"].get(symbol,0.0) + 1e-9 < qty:
                return jsonify({"ok": False, "error": f"insufficient {symbol} to place sell limit"}), 400
            store["balances"][symbol] -= qty
            order["reserved_qty"] = qty
        global_orderbook["limit_orders"].append(order)
        return jsonify({"ok": True, "placed": order})

@app.route("/api/cancel_order", methods=["POST"])
@login_required
def api_cancel_order():
    sid = current_session_id()
    store = ensure_user_store()
    payload = request.get_json() or request.form
    oid = payload.get("order_id")
    removed = False
    for o in list(global_orderbook["limit_orders"]):
        if o.get("id")==oid and o.get("session_id")==sid:
            if o.get("reserved_usdt"):
                store["balances"]["USDT"] += o["reserved_usdt"]
            if o.get("reserved_qty"):
                store["balances"][o["symbol"]] += o["reserved_qty"]
            global_orderbook["limit_orders"].remove(o)
            o["status"]="cancelled"
            store["orders"].append(o)
            removed = True
            break
    return jsonify({"ok": removed})

@app.route("/api/withdraw", methods=["POST"])
@login_required
def api_withdraw():
    """
    Simulated withdraw (send) of USDT to external address.
    Body: { amount: float, address: str, network: str, note: str (optional) }
    """
    sid = current_session_id()
    store = ensure_user_store()
    payload = request.get_json() or request.form
    try:
        amt = float(payload.get("amount") or 0.0)
    except:
        return jsonify({"ok": False, "error": "invalid amount"}), 400
    addr = (payload.get("address") or "").strip()
    network = (payload.get("network") or NETWORK_LABEL).strip()
    note = (payload.get("note") or "").strip()
    if amt <= 0:
        return jsonify({"ok": False, "error": "amount must be > 0"}), 400
    if not addr:
        return jsonify({"ok": False, "error": "address required"}), 400
    # basic address validation: allow addresses starting with 'T' for TRX or generic non-empty
    if network.upper().startswith("TRX") and not addr.startswith("T"):
        # not strict, just warn and reject
        return jsonify({"ok": False, "error": "TRX addresses typically start with 'T'"}), 400
    if store["balances"].get("USDT", 0.0) + 1e-9 < amt:
        return jsonify({"ok": False, "error": "insufficient USDT balance"}), 400
    # deduct and record transfer
    store["balances"]["USDT"] -= amt
    tx = {
        "id": str(uuid.uuid4()),
        "to": addr,
        "network": network,
        "amount": amt,
        "note": note,
        "status": "sent",
        "timestamp": int(time.time())
    }
    store["transfers"].append(tx)
    return jsonify({"ok": True, "tx": tx, "new_balance": store["balances"]["USDT"]})

@app.route("/api/cancel_withdraw", methods=["POST"])
@login_required
def api_cancel_withdraw():
    # simple cancellation if wanted - here we won't implement (withdrawals are immediate simulated)
    return jsonify({"ok": False, "error": "cancel not supported in simulation"}), 400

@app.route("/")
@login_required
def home():
    user = session.get("user", {"name":"User","email":""})
    if not market_cache.get("data"): fetch_prices_once()
    html = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>solfire — Exchange (vertical + search + send)</title>
<style>
:root{--bg:#071033;--muted:#94a3b8;--accent:#ffb703}
body{margin:0;font-family:Inter,Arial;background:linear-gradient(180deg,var(--bg),#020617);color:#e6eef8}
.container{max-width:820px;margin:12px auto;padding:12px}
.card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));padding:12px;border-radius:10px;margin-bottom:12px}
.header{display:flex;flex-direction:column;gap:8px}
.top-row{display:flex;align-items:center;justify-content:space-between;gap:8px}
.addr{font-family:monospace;font-weight:700}
.btn{padding:8px 10px;border-radius:8px;border:none;cursor:pointer}
.btn.primary{background:linear-gradient(90deg,var(--accent),#ff7b54);color:#071033;font-weight:700}
.small{color:var(--muted);font-size:13px}
.market-item{display:flex;align-items:center;justify-content:space-between;padding:10px;border-radius:8px;background:rgba(255,255,255,0.01);margin-bottom:8px}
.coin-left{display:flex;align-items:center;gap:10px}
.coin-img{width:36px;height:36px;border-radius:8px}
.search-row{display:flex;align-items:center;gap:8px;margin-top:12px}
.search-input{flex:1;padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.04);background:rgba(255,255,255,0.02);color:#e6eef8}
.search-icon{font-size:18px;color:var(--muted);padding:8px}
.modal{position:fixed;left:0;top:0;width:100%;height:100%;display:none;align-items:center;justify-content:center;background:rgba(2,6,23,0.6);z-index:60}
.modal.show{display:flex}
.modal-box{width:94%;max-width:760px;background:#071233;border-radius:10px;padding:12px}
input[type=number], input[type=text], select, textarea{padding:8px;border-radius:8px;border:1px solid rgba(255,255,255,0.04);background:rgba(255,255,255,0.02);color:#e6eef8;width:100%;box-sizing:border-box}
@media(max-width:600px){.container{padding:8px}}
.section-title{font-weight:800;margin-bottom:8px}
.card-sub{color:var(--muted);font-size:13px;margin-bottom:6px}
.transfer-item{padding:8px;border-radius:6px;background:rgba(255,255,255,0.01);margin-bottom:8px}
</style>
</head><body>
  <div class="container">
    <div class="card header">
      <div class="top-row">
        <div style="display:flex;flex-direction:column">
          <div style="font-weight:900;font-size:20px">solfire</div>
          <div class="small">Professional simulated exchange</div>
        </div>
        <div style="text-align:right">
          <div style="font-weight:700">{{ user.name }}</div>
          <div class="small">{{ user.email }}</div>
        </div>
      </div>

      <!-- BALANCE ON TOP -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:8px">
        <div>
          <div class="small">USDT BALANCE</div>
          <div id="usdtBalance" style="font-weight:900;font-size:20px">$0.00</div>
          <div class="card-sub">Available for trading and sending</div>
        </div>

        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
          <div class="addr" id="hdrWallet">{{ wallet }}</div>
          <div class="small">{{ network }}</div>
          <div style="display:flex;gap:6px;margin-top:6px">
            <button class="btn" onclick="copyHeaderAddress()">Copy</button>
            <button class="btn" onclick="openSendModal()">Send</button>
          </div>
        </div>
      </div>

      <!-- SEARCH -->
      <div class="search-row">
        <div class="search-icon">🔍</div>
        <input id="searchInput" class="search-input" placeholder="Search by symbol or name (e.g. BTC, bitcoin)"/>
      </div>
    </div>

    <!-- MARKETS LIST (vertical) -->
    <div class="card">
      <div class="section-title">Markets</div>
      <div class="card-sub">Live markets — prices update automatically</div>
      <div id="marketsList" style="margin-top:10px"></div>
    </div>

    <!-- ORDERS (vertical under markets) -->
    <div class="card">
      <div class="section-title">Orders</div>
      <div id="ordersArea" class="small">No orders yet.</div>
    </div>

    <!-- TRANSFERS -->
    <div class="card">
      <div class="section-title">Recent Transfers (Send)</div>
      <div id="transfersArea" class="small">No transfers yet.</div>
    </div>
  </div>

  <!-- trade modal -->
  <div id="tradeModal" class="modal"><div class="modal-box">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div id="tradeTitle" style="font-weight:900"></div>
      <button class="btn" onclick="closeTrade()">Close</button>
    </div>
    <div style="margin-top:10px;display:flex;gap:12px;flex-wrap:wrap">
      <div style="flex:1;min-width:220px">
        <div class="small">Price</div><div id="tradePrice" style="font-weight:900">$0.00</div>
        <div style="margin-top:8px"><select id="tradeType"><option value="market">Market</option><option value="limit">Limit</option></select></div>
        <div style="margin-top:8px"><select id="tradeSide"><option value="buy">Buy</option><option value="sell">Sell</option></select></div>
        <div style="margin-top:8px"><div class="small">Quantity</div><input id="tradeQty" type="number" step="any" value="0.001"/></div>
        <div id="limitField" style="display:none;margin-top:8px"><div class="small">Limit Price</div><input id="tradeLimit" type="number" step="any"/></div>
        <div style="margin-top:10px"><button class="btn primary" onclick="submitTrade()">Place Order</button></div>
        <div id="tradeMsg" style="margin-top:8px" class="small"></div>
      </div>

      <div style="width:300px;min-width:200px">
        <div class="small">Open Orders</div><div id="openOrders" style="margin-top:8px" class="small">No open orders.</div>
        <div style="margin-top:10px" class="small">Recent Trades</div><div id="recentTrades" style="margin-top:8px" class="small">No trades yet.</div>
      </div>
    </div>
  </div></div>

  <!-- send modal -->
  <div id="sendModal" class="modal"><div class="modal-box">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div style="font-weight:900">Send USDT</div>
      <button class="btn" onclick="closeSendModal()">Close</button>
    </div>
    <div style="margin-top:10px">
      <div class="small">Available: <span id="sendAvailable">$0.00</span></div>
      <div style="margin-top:8px"><label class="small">Amount (USDT)</label><input id="sendAmount" type="number" step="any" placeholder="0.00"/></div>
      <div style="margin-top:8px"><label class="small">Destination Address</label><input id="sendAddress" type="text" placeholder="T..."/></div>
      <div style="margin-top:8px"><label class="small">Network</label>
        <select id="sendNetwork"><option>TRX (TRC20)</option><option>ERC20</option><option>BEP20</option></select>
      </div>
      <div style="margin-top:8px"><label class="small">Note (optional)</label><textarea id="sendNote" rows="2" placeholder="Memo or note"></textarea></div>
      <div style="margin-top:12px"><button class="btn primary" onclick="doSend()">Send</button> <button class="btn" onclick="closeSendModal()">Cancel</button></div>
      <div id="sendMsg" style="margin-top:8px" class="small"></div>
    </div>
  </div></div>

<script>
const clientPoll = {{ client_poll }};
let marketData = {};
let marketKeys = [];
let currentSymbol = null;

async function fetchPrices(){
  try{
    const res = await fetch('/api/prices');
    const j = await res.json();
    marketData = j.data || {};
    marketKeys = Object.keys(marketData || {});
    renderMarkets();
  }catch(e){ console.error(e); }
}
async function fetchAccount(){
  try{
    const res = await fetch('/api/account');
    const j = await res.json();
    document.getElementById('usdtBalance').innerText = '$' + (Number(j.usdt||0)).toFixed(2);
    document.getElementById('sendAvailable').innerText = '$' + (Number(j.usdt||0)).toFixed(2);
    renderOrders(j.orders);
    renderTransfers(j.transfers || []);
  }catch(e){ console.error(e); }
}

function renderMarkets(){
  const container = document.getElementById('marketsList');
  container.innerHTML = '';
  const q = (document.getElementById('searchInput').value || '').trim().toLowerCase();
  for(const k of marketKeys){
    const it = marketData[k] || {};
    const sym = it.symbol || k;
    const name = (it.name || '').toLowerCase();
    const price = (it.price !== undefined && it.price !== null) ? Number(it.price) : null;
    const change = (it.change_24h !== undefined && it.change_24h !== null) ? Number(it.change_24h) : null;
    const img = it.image || 'https://via.placeholder.com/36';
    const match = !q || k.toLowerCase().includes(q) || sym.toLowerCase().includes(q) || name.includes(q);
    if(!match) continue;
    const el = document.createElement('div'); el.className='market-item';
    el.innerHTML = `<div class="coin-left"><img class="coin-img" src="${img}" alt="${sym}"><div><div style="font-weight:800">${k}</div><div class="small">${it.name || ''} (${sym})</div></div></div>
    <div style="text-align:right"><div style="font-weight:900">${price!==null? '$'+price.toFixed(6): '—'}</div><div class="${change!==null && change<0?'change-neg':'change-pos'} small">${change!==null? change.toFixed(2)+'%':''}</div><div style="margin-top:8px"><button class="btn" onclick="openTrade('${k}')">Trade</button></div></div>`;
    container.appendChild(el);
  }
}

function renderOrders(orders){
  const oa = document.getElementById('ordersArea'); oa.innerHTML = '';
  if(!orders || orders.length===0){ oa.innerHTML = '<div class="small">No orders yet.</div>'; return; }
  orders.slice().reverse().forEach(o=>{
    const d = document.createElement('div'); d.style.padding='8px'; d.style.borderRadius='6px'; d.style.marginBottom='6px'; d.style.background='rgba(255,255,255,0.01)';
    d.innerHTML = `<div style="font-weight:700">${o.side.toUpperCase()} ${o.quantity} ${o.symbol}</div><div class="small">${o.status} ${o.executed_price? '@ $'+Number(o.executed_price).toFixed(4): (o.limit_price? '@ $'+Number(o.limit_price).toFixed(4):'')}</div>`;
    oa.appendChild(d);
  });
}

function renderTransfers(transfers){
  const ta = document.getElementById('transfersArea'); ta.innerHTML = '';
  if(!transfers || transfers.length===0){ ta.innerHTML = '<div class="small">No transfers yet.</div>'; return; }
  transfers.slice().reverse().forEach(t=>{
    const el = document.createElement('div'); el.className='transfer-item';
    const dt = new Date((t.timestamp||0)*1000).toLocaleString();
    el.innerHTML = `<div style="font-weight:700">${t.amount} USDT → ${t.to}</div><div class="small">${t.network} • ${t.status} • ${dt}</div>`;
    ta.appendChild(el);
  });
}

function openTrade(sym){
  currentSymbol = sym;
  const it = marketData[sym] || {};
  document.getElementById('tradeTitle').innerText = 'Trade ' + sym;
  document.getElementById('tradePrice').innerText = it.price? '$'+Number(it.price).toFixed(6) : '—';
  document.getElementById('tradeQty').value = '0.001';
  document.getElementById('tradeLimit').value = it.price? Number(it.price).toFixed(6) : '';
  document.getElementById('tradeMsg').innerText = '';
  document.getElementById('openOrders').innerText = 'No open orders.';
  document.getElementById('recentTrades').innerText = 'No trades yet.';
  document.getElementById('tradeModal').classList.add('show');
  updateModalInfo();
}
function closeTrade(){ document.getElementById('tradeModal').classList.remove('show'); }

document.getElementById('searchInput').addEventListener('input', ()=>renderMarkets());
document.getElementById('tradeType').addEventListener('change',(e)=>{ document.getElementById('limitField').style.display = e.target.value==='limit' ? 'block' : 'none'; });

async function submitTrade(){
  const type = document.getElementById('tradeType').value;
  const side = document.getElementById('tradeSide').value;
  const qty = parseFloat(document.getElementById('tradeQty').value)||0;
  const limit = parseFloat(document.getElementById('tradeLimit').value)||undefined;
  if(qty<=0){ document.getElementById('tradeMsg').innerText='Quantity must be > 0'; return; }
  const body = { symbol: currentSymbol, side: side, type: type, quantity: qty };
  if(type==='limit') body.limit_price = limit;
  const res = await fetch('/api/place_order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j = await res.json();
  if(j.ok){
    document.getElementById('tradeMsg').innerText = 'Order placed/executed';
    await fetchAccount(); await fetchPrices();
    updateModalInfo();
  } else {
    document.getElementById('tradeMsg').innerText = 'Error: ' + (j.error||'unknown');
  }
}

async function updateModalInfo(){
  try{
    const res = await fetch('/api/account'); const j = await res.json();
    const open = (j.orders||[]).filter(o=>o.symbol===currentSymbol && (o.status==='open' || o.status==='placed' || o.status==='pending'));
    const openDiv = document.getElementById('openOrders'); openDiv.innerHTML = ''; if(open.length===0) openDiv.innerText='No open orders'; else open.forEach(o=>{ const e=document.createElement('div'); e.className='small'; e.innerText=`${o.side.toUpperCase()} ${o.quantity} ${o.status}`; openDiv.appendChild(e);});
    const trades = (j.trades||[]).filter(t=>t.symbol===currentSymbol).slice().reverse().slice(0,20);
    const td = document.getElementById('recentTrades'); td.innerHTML = ''; if(trades.length===0) td.innerText='No trades'; else trades.forEach(t=>{ const e=document.createElement('div'); e.className='small'; e.innerText=`${t.side.toUpperCase()} ${t.quantity} @ $${Number(t.price).toFixed(4)}`; td.appendChild(e);});
  }catch(e){ console.error(e); }
}

// Send modal functions
function openSendModal(){
  document.getElementById('sendAmount').value = '';
  document.getElementById('sendAddress').value = '';
  document.getElementById('sendNote').value = '';
  document.getElementById('sendMsg').innerText = '';
  document.getElementById('sendModal').classList.add('show');
}
function closeSendModal(){ document.getElementById('sendModal').classList.remove('show'); }

async function doSend(){
  const amount = parseFloat(document.getElementById('sendAmount').value) || 0;
  const address = document.getElementById('sendAddress').value.trim();
  const network = document.getElementById('sendNetwork').value;
  const note = document.getElementById('sendNote').value.trim();
  if(amount <= 0){ document.getElementById('sendMsg').innerText = 'Enter valid amount'; return; }
  if(!address){ document.getElementById('sendMsg').innerText = 'Enter destination address'; return; }
  // Basic TRX address check when network is TRX
  if(network.toUpperCase().startsWith('TRX') && !address.startsWith('T')){ document.getElementById('sendMsg').innerText = 'TRX addresses typically start with T'; return; }
  const res = await fetch('/api/withdraw', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({amount: amount, address: address, network: network, note: note})});
  const j = await res.json();
  if(j.ok){
    document.getElementById('sendMsg').innerText = 'Sent (simulated).';
    await fetchAccount();
    setTimeout(()=>{ closeSendModal(); }, 900);
  } else {
    document.getElementById('sendMsg').innerText = 'Error: ' + (j.error || 'unknown');
  }
}

function copyHeaderAddress(){ const t = document.getElementById('hdrWallet').innerText; navigator.clipboard.writeText(t).then(()=>alert('Address copied')) }

async function fetchAccount(){ try{ const r = await fetch('/api/account'); const j = await r.json(); document.getElementById('usdtBalance').innerText = '$'+Number(j.usdt||0).toFixed(2); document.getElementById('sendAvailable').innerText = '$'+Number(j.usdt||0).toFixed(2); renderOrders(j.orders); renderTransfers(j.transfers||[]);}catch(e){ console.error(e); } }
async function fetchPricesAndAccount(){ await fetchPrices(); await fetchAccount(); }

fetchPricesAndAccount();
setInterval(fetchPricesAndAccount, clientPoll);
</script>
</body></html>
"""
    return render_template_string(html, user=user, wallet=WALLET_ADDRESS, network=NETWORK_LABEL, client_poll=CLIENT_POLL_MS)

# ---------- run ----------
if __name__ == "__main__":
    # تشغيل جلب الأسعار لأول مرة
    fetch_prices_once()
    
    # الحصول على المنفذ من الخادم بشكل ديناميكي
    # إذا لم يجد منفذ (تشغيل محلي) سيستخدم 5000 تلقائياً
    port = int(os.environ.get("PORT", 5000))
    
    # تشغيل التطبيق
    app.run(host="0.0.0.0", port=port, debug=False)

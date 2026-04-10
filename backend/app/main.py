from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import requests
import asyncio
from datetime import datetime
import threading

app = FastAPI(title="QuantAgent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KRAKEN_API = "https://api.kraken.com/0/public/OHLC"
SYMBOL = "BTCUSD"
TIMEFRAME = 5
INITIAL_CAPITAL = 10000.0

state = {
    "running": False,
    "price": 0.0,
    "signal": "HOLD",
    "confidence": 0.0,
    "position_size": 0.0,
    "pnl": 0.0,
    "drawdown": 0.0,
    "risk_status": "OK",
    "trades": [],
    "signals": [],
    "equity": [INITIAL_CAPITAL],
    "trade_history": [],
    "risk_checks": [],
    "validation_logs": [],
    "circuit_breaker_events": [],
    "consecutive_losses": 0,
}

ws_clients = []
trading_thread = None
stop_event = threading.Event()

def fetch_data():
    try:
        r = requests.get(KRAKEN_API, params={"pair": SYMBOL, "interval": TIMEFRAME}, timeout=10)
        data = r.json()
        if "result" in data:
            pair = list(data["result"].keys())[0]
            ohlcv = data["result"][pair]
            df = pd.DataFrame(ohlcv, columns=["time","open","high","low","close","vol","trades"])
            df["close"] = df["close"].astype(float)
            return df
    except Exception as e:
        print("Fetch error:", e)
    return None

def calc_indicators(df):
    if df is None or len(df) < 20:
        return df
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).ewm(span=14).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(span=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    df["bb_mid"] = df["close"].rolling(20).mean()
    df["bb_std"] = df["close"].rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
    return df

def generate_signal(row):
    rsi = row.get("rsi")
    close = row.get("close")
    bb_upper = row.get("bb_upper")
    bb_lower = row.get("bb_lower")
    if pd.isna(rsi) or pd.isna(bb_upper):
        return "HOLD", 0
    if rsi <= 30 and close <= bb_lower * 1.01:
        return "BUY", 80
    if rsi >= 70 and close >= bb_upper * 0.99:
        return "SELL", 80
    return "HOLD", 20

def trading_loop():
    while not stop_event.is_set():
        try:
            df = fetch_data()
            if df is None or len(df) < 20:
                continue
            df = calc_indicators(df)
            row = df.iloc[-1]
            sig, conf = generate_signal(row)
            state["price"] = float(row["close"])
            state["signal"] = sig
            state["confidence"] = conf
            if sig == "BUY" and state["position_size"] == 0:
                state["position_size"] = 0.01
                state["trades"].append({"time": str(datetime.now()), "type": "BUY", "price": row["close"], "pnl": 0})
                state["trade_history"].append({"entry_time": str(datetime.now()), "entry_price": row["close"], "size": 0.01, "pnl": 0, "return_pct": 0, "reason": "BUY"})
                state["validation_logs"].append({"time": str(datetime.now()), "event": f"BUY signal at ${row['close']}"})
            elif sig == "SELL" and state["position_size"] > 0:
                pnl = (row["close"] - state["trades"][-1]["price"]) * state["position_size"]
                state["pnl"] += pnl
                state["equity"].append(state["equity"][-1] + pnl)
                state["trades"].append({"time": str(datetime.now()), "type": "SELL", "price": row["close"], "pnl": pnl})
                state["trade_history"].append({"exit_time": str(datetime.now()), "exit_price": row["close"], "pnl": pnl, "return_pct": (pnl / (state["trades"][-1]["price"] * 0.01)) * 100, "reason": "SELL"})
                state["position_size"] = 0
                state["validation_logs"].append({"time": str(datetime.now()), "event": f"SELL signal at ${row['close']}, PnL: ${pnl}"})
            if state["equity"]:
                peak = max(state["equity"])
                state["drawdown"] = (peak - state["equity"][-1]) / peak if peak > 0 else 0
                state["risk_status"] = "WARNING" if state["drawdown"] > 0.05 else "OK"
            state["signals"].append({"time": str(datetime.now()), "signal": sig, "confidence": conf})
            for client in ws_clients:
                try:
                    asyncio.run(client.send_json(state))
                except:
                    pass
        except Exception as e:
            print("Loop error:", e)
        stop_event.wait(2)

@app.get("/")
def root():
    return {"status": "QuantAgent running"}

@app.post("/run-demo")
def run_demo():
    global trading_thread
    if not state["running"]:
        state["running"] = True
        state["trades"] = []
        state["signals"] = []
        state["equity"] = [INITIAL_CAPITAL]
        state["trade_history"] = []
        state["risk_checks"] = [{"check": "drawdown", "value": 0, "status": "OK"}]
        state["validation_logs"] = []
        state["circuit_breaker_events"] = []
        state["consecutive_losses"] = 0
        stop_event.clear()
        trading_thread = threading.Thread(target=trading_loop, daemon=True)
        trading_thread.start()
    return {"status": "Demo started", "trades": len(state["trades"])}

@app.get("/state")
def get_state():
    return state

@app.get("/trades")
def get_trades():
    return {"trades": state["trades"]}

@app.get("/pnl")
def get_pnl():
    return {"pnl": state["pnl"], "equity": state["equity"], "drawdown": state["drawdown"]}

@app.get("/signals")
def get_signals():
    return {"signals": state["signals"]}

@app.get("/trust-panel")
def trust_panel():
    return {
        "trade_history": state["trade_history"],
        "validation_logs": state["validation_logs"],
        "risk_checks": state["risk_checks"],
        "circuit_breaker_events": state["circuit_breaker_events"],
        "consecutive_losses": state["consecutive_losses"]
    }

@app.websocket("/ws/updates")
async def ws_updates(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            await websocket.send_json(state)
            await asyncio.sleep(1)
    except:
        pass
    finally:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
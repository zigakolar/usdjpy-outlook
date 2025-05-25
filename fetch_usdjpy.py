#!/usr/bin/env python3
import os
import json
import openai
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone

# -----------------------
# 2) High-impact U.S. events (Trading Economics guest key)
# -----------------------

today = datetime.now(timezone.utc).date().isoformat()

te_url = (
    "https://api.tradingeconomics.com/calendar"
    "?c=guest:guest"                      # free guest key
    "&country=United%20States"
    f"&start={today}&end={today}"
)
cal_resp = requests.get(te_url, timeout=10)

if cal_resp.status_code == 200:
    cal_events = cal_resp.json()
else:
    print(f"TradingEconomics calendar fetch failed ({cal_resp.status_code}); defaulting to none")
    cal_events = []

keywords = ("FOMC", "Fed", "Federal Funds", "Nonfarm", "Payroll", "CPI", "Consumer Price")
high_events = [e["Event"] for e in cal_events
               if e.get("Country") == "United States" and any(k in e["Event"] for k in keywords)]

high_vol_event = ", ".join(high_events) if high_events else "None"

# -----------------------
# 3) Pull USDJPY (JPY=X) and DXY intraday data
# ----------------------- (JPY=X) and DXY intraday data
# -----------------------

def fetch_intraday(symbol:str):
    df = yf.download(symbol, period="7d", interval="1h", progress=False)
    hi, lo, cl = df["High"], df["Low"], df["Close"]
    pc = cl.shift(1)
    tr = pd.concat([
        hi - lo,
        (hi - pc).abs(),
        (lo - pc).abs()
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.rolling(14).mean()
    pivot = (hi + lo + cl) / 3
    s1 = 2 * pivot - hi
    r1 = 2 * pivot - lo
    last = df.dropna().iloc[-1]
    idx  = last.name
    return {
        "open":  float(last["Open"]),
        "high":  float(last["High"]),
        "low":   float(last["Low"]),
        "close": float(last["Close"]),
        "atr":   float(last["ATR14"]),
        "s1":    float(s1.loc[idx]),
        "r1":    float(r1.loc[idx])
    }

usdjpy = fetch_intraday("JPY=X")
dxy    = fetch_intraday("DX-Y.NYB")  # ICE dollar index ticker on Yahoo

# -----------------------
# 4) Compute SL/TP for USDJPY
# -----------------------
stop_loss     = usdjpy["s1"] - usdjpy["atr"]
take_profit_1 = usdjpy["r1"] + 0.5 * usdjpy["atr"]
take_profit_2 = usdjpy["r1"] + 1.0 * usdjpy["atr"]

# -----------------------
# 5) Build LLM prompt
# -----------------------

prompt = f"""
SYSTEM: You are a professional intraday FX strategist.

USD/JPY 1‑hour stats:
  Open={usdjpy['open']:.4f}, High={usdjpy['high']:.4f}, Low={usdjpy['low']:.4f}, Close={usdjpy['close']:.4f}
  ATR14={usdjpy['atr']:.4f}, Pivot S1={usdjpy['s1']:.4f}, Pivot R1={usdjpy['r1']:.4f}

DXY 1‑hour stats (broad USD gauge):
  Close={dxy['close']:.2f}, ATR14={dxy['atr']:.2f}, Pivot S1={dxy['s1']:.2f}, Pivot R1={dxy['r1']:.2f}

Today's high‑volatility U.S. event: {high_vol_event}

Using only these numbers:
- Choose direction for USD/JPY (Long | Short | Neutral) taking DXY bias into account.
- Provide stop_loss, take_profit_1, take_profit_2 (already computed above, but you may confirm they align with bias).
- Give next_window bias or key level for next 4–8 hours.
- Summary (2 sentences) must mention DXY perspective (e.g., "DXY strength supports USDJPY longs").

Respond ONLY with JSON exactly:
{{
  "direction": "Long|Short|Neutral",
  "stop_loss": {stop_loss:.4f},
  "take_profit_1": {take_profit_1:.4f},
  "take_profit_2": {take_profit_2:.4f},
  "high_volatility_report": "{high_vol_event}",
  "next_window": "...",
  "summary": "..."
}}
NO extra text.
"""

# -----------------------
# 6) Call OpenAI
# -----------------------
try:
    resp = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a professional intraday FX strategist."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0
    )
    data = json.loads(resp.choices[0].message.content.strip())
except Exception as e:
    print("OpenAI API error, using fallback:", e)
    data = {
        "direction": "Neutral",
        "stop_loss": round(stop_loss, 4),
        "take_profit_1": round(take_profit_1, 4),
        "take_profit_2": round(take_profit_2, 4),
        "high_volatility_report": high_vol_event,
        "next_window": "",
        "summary": ""
    }

# -----------------------
# 7) Write JSON
# -----------------------
with open("usdjpy.json", "w") as f:
    json.dump(data, f, indent=2)
print("Wrote usdjpy.json:", data)

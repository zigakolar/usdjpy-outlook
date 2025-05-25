#!/usr/bin/env python3
import os
import json
import openai
import yfinance as yf
import pandas as pd
from datetime import datetime

# 1) Load API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

# 2) Detect today’s high-volatility event (simplified)
today = datetime.utcnow().date()
high_vol_event = None
# NFP: first Friday of month (approx days 1–7, weekday=4)
if today.weekday() == 4 and 1 <= today.day <= 7:
    high_vol_event = "NFP"
# CPI: second Tuesday (approx days 8–14, weekday=1)
elif today.weekday() == 1 and 8 <= today.day <= 14:
    high_vol_event = "CPI"
# FOMC placeholder (requires calendar API)
# elif matches FOMC schedule:
#     high_vol_event = "FOMC"

# 3) Fetch intraday data (1h) and compute ATR(14) + pivots manually
df = yf.download("JPY=X", period="7d", interval="1h", progress=False)
# Prepare price series
high = df['High']
low = df['Low']
close = df['Close']
# Compute True Range components
pc = close.shift(1)
tr1 = high - low
tr2 = (high - pc).abs()
tr3 = (low - pc).abs()
# Combine and compute TR
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
df['TR'] = tr
# ATR(14)
df['ATR14'] = df['TR'].rolling(window=14).mean()
# Pivot, S1, R1
pivot = (high + low + close) / 3
df['pivot'] = pivot
df['S1'] = 2 * pivot - high
df['R1'] = 2 * pivot - low

# 4) Extract latest bar as a scalar Series
last = df.dropna().iloc[-1]
O = last['Open']
H = last['High']
L = last['Low']
C = last['Close']
atr = last['ATR14']
s1 = last['S1']
r1 = last['R1']

# 5) Calculate SL/TP levels based on ATR + pivots
stop_loss     = s1 - atr
take_profit_1 = r1 + 0.5 * atr
take_profit_2 = r1 + 1.0 * atr
stop_loss     = s1 - atr
take_profit_1 = r1 + 0.5 * atr
take_profit_2 = r1 + 1.0 * atr
stop_loss     = s1 - atr
take_profit_1 = r1 + 0.5 * atr
take_profit_2 = r1 + 1.0 * atr

# 5) Build prompt with live values using explicit float casts to ensure scalar formatting
prompt = f"""
SYSTEM: You are a professional intraday FX strategist.

Here are the latest 1-hour USD/JPY values:
  Open={float(O):.4f}, High={float(H):.4f}, Low={float(L):.4f}, Close={float(C):.4f}
  ATR(14): {float(atr):.4f}
  Pivot S1: {float(s1):.4f}, Pivot R1: {float(r1):.4f}
Today's high-volatility event: {json.dumps(high_vol_event)}

Using only these data points (no other news), determine:
- direction: "Long" | "Short" | "Neutral"
- stop_loss: just beyond S1 minus 1×ATR (provided above as {float(stop_loss):.4f})
- take_profit_1: just beyond R1 plus 0.5×ATR (provided above as {float(take_profit_1):.4f})
- take_profit_2: just beyond R1 plus 1×ATR (provided above as {float(take_profit_2):.4f})
- next_window: bias or key level for the next 4–8 hours
- summary: up to 2 sentences

Respond ONLY with valid JSON exactly:
{{
  "direction": "Long|Short|Neutral",
  "stop_loss": {float(stop_loss):.4f},
  "take_profit_1": {float(take_profit_1):.4f},
  "take_profit_2": {float(take_profit_2):.4f},
  "high_volatility_report": {json.dumps(high_vol_event)},
  "next_window": "...",
  "summary": "..."
}}
NO extra text.
"""

# 6) Call OpenAI and parse response and parse response
try:
    resp = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a professional intraday FX strategist."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0
    )
    content = resp.choices[0].message.content.strip()
    data = json.loads(content)
except Exception as e:
    print(f"OpenAI API error, defaulting fallback: {e}")
    data = {
        "direction": "Neutral",
        "stop_loss": round(stop_loss,4),
        "take_profit_1": round(take_profit_1,4),
        "take_profit_2": round(take_profit_2,4),
        "high_volatility_report": high_vol_event,
        "next_window": "",
        "summary": ""
    }

# 7) Write JSON to file
with open("usdjpy.json", "w") as f:
    json.dump(data, f, indent=2)

print("Wrote usdjpy.json:", data)

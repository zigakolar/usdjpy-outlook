#!/usr/bin/env python3
import os
import json
import openai
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone

# -----------------------
# 1) Load API keys
# -----------------------
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

fmp_api_key = os.getenv("FMP_API_KEY")
if not fmp_api_key:
    raise RuntimeError("FMP_API_KEY not set")

# -----------------------
# 2) Get today's high-impact US events via FMP
# -----------------------

today = datetime.now(timezone.utc).date().isoformat()
url = (
    "https://financialmodelingprep.com/stable/economic-calendar"
    f"?from={today}&to={today}&apikey={fmp_api_key}"
)
resp = requests.get(url, timeout=10)

if resp.status_code == 200:
    events = resp.json()
elif resp.status_code == 402:
    print("Warning: FMP quota/billing issue (402). Using no events.")
    events = []
else:
    print(f"Warning: FMP calendar fetch failed ({resp.status_code}). Using no events.")
    events = []

high_events = [e["event"] for e in events if e.get("country") == "United States" and e.get("impact") == "High"]
high_vol_event = ", ".join(high_events) if high_events else "None"

# -----------------------
# 3) Fetch 1-hour USDJPY data and compute ATR & pivots
# -----------------------

df = yf.download("JPY=X", period="7d", interval="1h", progress=False)

high = df["High"]
low  = df["Low"]
close= df["Close"]

prior_close = close.shift(1)
tr = pd.concat([
    high - low,
    (high - prior_close).abs(),
    (low  - prior_close).abs()
], axis=1).max(axis=1)

df["ATR14"] = tr.rolling(14).mean()

pivot = (high + low + close) / 3
s1_series = 2 * pivot - high
r1_series = 2 * pivot - low

last = df.dropna().iloc[-1]
idx = last.name

O, H, L, C = map(float, [last["Open"], last["High"], last["Low"], last["Close"]])
atr = float(last["ATR14"])
s1  = float(s1_series.loc[idx])
r1  = float(r1_series.loc[idx])

# -----------------------
# 4) Calculate SL/TP
# -----------------------
stop_loss     = s1 - atr
take_profit_1 = r1 + 0.5 * atr
take_profit_2 = r1 + 1.0 * atr

# -----------------------
# 5) Build LLM prompt
# -----------------------

prompt = f"""
SYSTEM: You are a professional intraday FX strategist.

Here are the latest 1-hour USD/JPY stats:
  Open={O:.4f}, High={H:.4f}, Low={L:.4f}, Close={C:.4f}
  ATR14={atr:.4f}
  Pivot S1={s1:.4f}, Pivot R1={r1:.4f}
Today's high-volatility report: {high_vol_event}

Using only these numbers, output JSON:
{{
  \"direction\": \"Long|Short|Neutral\",
  \"stop_loss\": {stop_loss:.4f},
  \"take_profit_1\": {take_profit_1:.4f},
  \"take_profit_2\": {take_profit_2:.4f},
  \"high_volatility_report\": \"{high_vol_event}\",
  \"next_window\": \"...\",
  \"summary\": \"...\"
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
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    content = resp.choices[0].message.content.strip()
    data = json.loads(content)
except Exception as e:
    print("OpenAI API error, using fallback:", e)
    data = {
        "direction": "Neutral",
        "stop_loss": round(stop_loss,4),
        "take_profit_1": round(take_profit_1,4),
        "take_profit_2": round(take_profit_2,4),
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

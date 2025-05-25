#!/usr/bin/env python3
import os
import json
import openai
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# Load API keys
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

fmp_api_key = os.getenv("FMP_API_KEY")
if not fmp_api_key:
    raise RuntimeError("FMP_API_KEY not set")

# Fetch today's USD economic calendar events from FMP
today = datetime.utcnow().date().isoformat()
url = (
    f"https://financialmodelingprep.com/stable/economic-calendar"
    f"?from={today}&to={today}&apikey={fmp_api_key}"
)
response = requests.get(url, timeout=10)
if response.status_code == 200:
    events = response.json()
elif response.status_code == 402:
    print(f"Warning: FMP API access issue ({response.status_code}); defaulting to no events")
    events = []
else:
    print(f"Warning: FMP calendar fetch failed with status {response.status_code}; defaulting to no events")
    events = []

# Filter for high-impact US events
high_events = [e['event'] for e in events
               if e.get('country') == 'United States' and e.get('impact') == 'High']
high_vol_event = ", ".join(high_events) if high_events else "None"

# Fetch intraday data (1h) and compute ATR(14) + pivots
symbol = "JPY=X"
df = yf.download(symbol, period="7d", interval="1h", progress=False)
high = df['High']
low = df['Low']
close = df['Close']

# True Range components
prior_close = close.shift(1)
tr1 = high - low
tr2 = (high - prior_close).abs()
tr3 = (low - prior_close).abs()
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
df['ATR14'] = tr.rolling(window=14).mean()

# Compute pivot, S1, and R1 series without assigning to DataFrame
pivot_series = (high + low + close) / 3
s1_series = 2 * pivot_series - high
r1_series = 2 * pivot_series - low

# Extract latest bar as scalars
last = df.dropna().iloc[-1]
O = last['Open']
H = last['High']
L = last['Low']
C = last['Close']
atr = last['ATR14']
# Extract corresponding pivot, S1, and R1 for the latest bar
latest_idx = last.name
s1 = s1_series.loc[latest_idx]
r1 = r1_series.loc[latest_idx]
last = df.dropna().iloc[-1]
O = last['Open']
H = last['High']
L = last['Low']
C = last['Close']
atr = last['ATR14']
s1 = last['S1']
r1 = last['R1']

# Calculate SL/TP levels based on ATR + pivots
stop_loss = s1 - atr
take_profit_1 = r1 + 0.5 * atr
take_profit_2 = r1 + 1.0 * atr

# Build prompt with live values
prompt = f"""
SYSTEM: You are a professional intraday FX strategist.

Here are the latest 1-hour USD/JPY values:
  Open={O:.4f}, High={H:.4f}, Low={L:.4f}, Close={C:.4f}
  ATR(14)={atr:.4f}
  Pivot S1={s1:.4f}, Pivot R1={r1:.4f}
Today's high-volatility report: {high_vol_event}

Using only these data points, determine:
- direction: "Long" | "Short" | "Neutral"
- stop_loss: just beyond S1 minus 1×ATR
- take_profit_1: just beyond R1 plus 0.5×ATR
- take_profit_2: just beyond R1 plus 1×ATR
- next_window: bias or key level for the next 4–8 hours
- summary: up to 2 sentences

Respond ONLY with valid JSON exactly:
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

# Call OpenAI and parse response
try:
    resp = openai.ChatCompletion.create(
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
    print(f"OpenAI API error: {e}")
    data = {
        "direction": "Neutral",
        "stop_loss": round(stop_loss, 4),
        "take_profit_1": round(take_profit_1, 4),
        "take_profit_2": round(take_profit_2, 4),
        "high_volatility_report": high_vol_event,
        "next_window": "",
        "summary": ""
    }

# Write JSON to file
with open("usdjpy.json", "w") as f:
    json.dump(data, f, indent=2)

print("Wrote usdjpy.json:", data)

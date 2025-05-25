Below are the two updated files needed to fetch today’s USD economic calendar events (NFP, CPI, FOMC) from FinancialModelingPrep and integrate them into your GitHub Actions pipeline.

---

**.github/workflows/update\_usdjpy.yml**

```yaml
name: Update USDJPY Intraday Outlook

on:
  schedule:
    # Run hourly between 05:00 and 16:00 UTC
    - cron: '0 5-16 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          persist-credentials: true

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: |
          python3 -m pip install --upgrade pip setuptools wheel
          pip install openai yfinance pandas requests

      - name: Fetch USDJPY direction
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          FMP_API_KEY: ${{ secrets.FMP_API_KEY }}   # Add your FMP key as a GitHub secret
        run: python3 fetch_usdjpy.py

      - name: Debug JSON
        run: cat usdjpy.json

      - name: Commit JSON
        uses: EndBug/add-and-commit@v9
        with:
          author_name: github-actions[bot]
          author_email: github-actions[bot]@users.noreply.github.com
          message: "Hourly update of USDJPY outlook with economic calendar"
          add: "usdjpy.json"
```

---

**fetch\_usdjpy.py**

```python
#!/usr/bin/env python3
import os
import json
import openai
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# 1) Load API keys
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")
FMP_API_KEY = os.getenv("FMP_API_KEY")
if not FMP_API_KEY:
    raise RuntimeError("FMP_API_KEY not set")

# 2) Fetch today’s USD economic calendar events from FMP
today = datetime.utcnow().date().isoformat()
url = (
    f"https://financialmodelingprep.com/stable/economic-calendar"
    f"?from={today}&to={today}&apikey={FMP_API_KEY}"
)
resp = requests.get(url, timeout=10)
if resp.status_code != 200:
    raise RuntimeError(f"FMP calendar fetch failed: {resp.status_code}")
events = resp.json()
# Filter for high-impact US events
high_events = [e['event'] for e in events
               if e.get('country') == 'United States' and e.get('impact') == 'High']
high_vol_event = ', '.join(high_events) if high_events else 'None'

# 3) Fetch intraday data (1h) and compute ATR(14) + pivots
symbol = "JPY=X"
df = yf.download(symbol, period="7d", interval="1h", progress=False)
high = df['High']; low = df['Low']; close = df['Close']
# True Range
pc = close.shift(1)
tr1 = high - low
tr2 = (high - pc).abs()
tr3 = (low - pc).abs()
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
df['ATR14'] = tr.rolling(window=14).mean()
# Pivot
pivot = (high + low + close) / 3
s1 = 2 * pivot - high	r1 = 2 * pivot - low

# 4) Extract latest scalar values
last = df.dropna().iloc[-1]
O, H, L, C = last['Open'], last['High'], last['Low'], last['Close']
atr, s1, r1 = last['ATR14'], last['S1'], last['R1']

# 5) Calculate SL/TP levels
stop_loss = s1 - atr
take_profit_1 = r1 + 0.5 * atr
take_profit_2 = r1 + 1.0 * atr

# 6) Build prompt with live values
prompt = f"""
SYSTEM: You are a professional intraday FX strategist.

Here are the latest 1-hour USD/JPY values:
  Open={float(O):.4f}, High={float(H):.4f}, Low={float(L):.4f}, Close={float(C):.4f}
  ATR(14)={float(atr):.4f}
  Pivot S1={float(s1):.4f}, Pivot R1={float(r1):.4f}
Today's high-volatility report: {json.dumps(high_vol_event)}

Using only these data points, determine the JSON:
{{
  "direction":"Long|Short|Neutral",
  "stop_loss":{float(stop_loss):.4f},
  "take_profit_1":{float(take_profit_1):.4f},
  "take_profit_2":{float(take_profit_2):.4f},
  "high_volatility_report":{json.dumps(high_vol_event)},
  "next_window":"...",
  "summary":"..."
}}
NO extra text.
"""

# 7) Call OpenAI and parse response\ ntry:
    resp = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role":"system","content":"You are a professional intraday FX strategist."},
            {"role":"user","content":prompt}
        ],
        temperature=0
    )
    content = resp.choices[0].message.content.strip()
    data = json.loads(content)
except Exception as e:
    print(f"OpenAI API error: {e}")
    data = {
        "direction":"Neutral",
        "stop_loss": round(stop_loss,4),
        "take_profit_1": round(take_profit_1,4),
        "take_profit_2": round(take_profit_2,4),
        "high_volatility_report":high_vol_event,
        "next_window":"",
        "summary":""
    }

# 8) Write JSON
with open("usdjpy.json","w") as f:
    json.dump(data,f,indent=2)
print("Wrote usdjpy.json:", data)
```

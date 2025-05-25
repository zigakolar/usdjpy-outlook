#!/usr/bin/env python3
import os, json, requests, yfinance as yf, pandas as pd, openai
from datetime import datetime, timezone

# ────────────────────────────────────────────────────────────────
# 1)  API KEYS
# ────────────────────────────────────────────────────────────────
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

fmp_api_key = os.getenv("FMP_API_KEY")
if not fmp_api_key:
    raise RuntimeError("FMP_API_KEY not set")

# ────────────────────────────────────────────────────────────────
# 2)  HIGH-IMPACT U.S. EVENTS (FMP ECON CAL)
# ────────────────────────────────────────────────────────────────
today = datetime.now(timezone.utc).date().isoformat()
cal_url = (
    "https://financialmodelingprep.com/stable/economic-calendar"
    f"?from={today}&to={today}&apikey={fmp_api_key}"
)
cal_resp = requests.get(cal_url, timeout=10)
cal_events = cal_resp.json() if cal_resp.status_code == 200 else []
high_events = [
    e["event"] for e in cal_events
    if e.get("country") == "United States" and e.get("impact") == "High"
]
high_vol_event = ", ".join(high_events) if high_events else "None"

# ────────────────────────────────────────────────────────────────
# 3)  FETCH INTRADAY DATA (USDJPY & DXY)
# ────────────────────────────────────────────────────────────────
def fetch_intraday(symbol: str):
    df = yf.download(symbol, period="7d", interval="1h", progress=False)
    hi, lo, cl = df["High"], df["Low"], df["Close"]
    pc = cl.shift(1)
    tr = pd.concat(
        [hi - lo, (hi - pc).abs(), (lo - pc).abs()], axis=1
    ).max(axis=1)
    df["ATR14"] = tr.rolling(14).mean()
    pivot = (hi + lo + cl) / 3
    s1 = 2 * pivot - hi
    r1 = 2 * pivot - lo
    last = df.dropna().iloc[-1]
    idx = last.name
    return {
        "open":  last["Open"].item(),
        "high":  last["High"].item(),
        "low":   last["Low"].item(),
        "close": last["Close"].item(),
        "atr":   last["ATR14"].item(),
        "s1":    s1.loc[idx].item(),
        "r1":    r1.loc[idx].item()
    }

usdjpy = fetch_intraday("JPY=X")
dxy    = fetch_intraday("DX-Y.NYB")   # ICE US-Dollar Index

# ────────────────────────────────────────────────────────────────
# 4)  SL / TP FOR USDJPY
# ────────────────────────────────────────────────────────────────
stop_loss     = usdjpy["s1"] - usdjpy["atr"]
take_profit_1 = usdjpy["r1"] + 0.5 * usdjpy["atr"]
take_profit_2 = usdjpy["r1"] + 1.0 * usdjpy["atr"]

# ────────────────────────────────────────────────────────────────
# 5)  BUILD PROMPT
# ────────────────────────────────────────────────────────────────
prompt = f"""
SYSTEM: You are a professional intraday FX strategist.

USD/JPY 1-hour:
  Open={usdjpy['open']:.4f}, High={usdjpy['high']:.4f}, Low={usdjpy['low']:.4f}, Close={usdjpy['close']:.4f}
  ATR14={usdjpy['atr']:.4f},  Pivot S1={usdjpy['s1']:.4f}, Pivot R1={usdjpy['r1']:.4f}

DXY 1-hour (broad USD gauge):
  Close={dxy['close']:.2f}, ATR14={dxy['atr']:.2f}, Pivot S1={dxy['s1']:.2f}, Pivot R1={dxy['r1']:.2f}

High-vol U.S. event today: {high_vol_event}

Using only these numbers:
• Pick USD/JPY direction (Long | Short | Neutral) **considering DXY bias**.
• stop_loss / TP1 / TP2 are given; ensure they match your bias.
• Give next_window bias or key level for next 4-8 h.
• Summary (2 sentences) **must mention DXY perspective**.

Respond ONLY with JSON:
{{
  "direction":"Long|Short|Neutral",
  "stop_loss":{stop_loss:.4f},
  "take_profit_1":{take_profit_1:.4f},
  "take_profit_2":{take_profit_2:.4f},
  "high_volatility_report":"{high_vol_event}",
  "next_window":"...",
  "summary":"..."
}}
NO extra text.
"""

# ────────────────────────────────────────────────────────────────
# 6)  CALL OPENAI (FORCE JSON)
# ────────────────────────────────────────────────────────────────
try:
    resp = openai.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[
            {"role": "system", "content": "You are a professional intraday FX strategist."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )
    data = json.loads(resp.choices[0].message.content)
except Exception as e:
    print("OpenAI API error → fallback:", e)
    data = {
        "direction": "Neutral",
        "stop_loss": round(stop_loss, 4),
        "take_profit_1": round(take_profit_1, 4),
        "take_profit_2": round(take_profit_2, 4),
        "high_volatility_report": high_vol_event,
        "next_window": "",
        "summary": ""
    }

# ────────────────────────────────────────────────────────────────
# 7)  WRITE JSON
# ────────────────────────────────────────────────────────────────
with open("usdjpy.json", "w") as f:
    json.dump(data, f, indent=2)

print("Wrote usdjpy.json:", data)

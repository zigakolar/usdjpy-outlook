#!/usr/bin/env python3
import os, json

# Try importing OpenAI; if it’s not available or fails, we’ll fall back
try:
    import openai
except ImportError:
    openai = None

# Always available fallback libs
import yfinance as yf
import pandas_ta as ta

# 1) Attempt LLM call if key & library present
direction = None
api_key = os.getenv("OPENAI_API_KEY")
if openai and api_key:
    openai.api_key = api_key
    try:
        resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":""},
                {"role":"user","content":"Provide today’s USD/JPY market direction only: long, short, or neutral."}
            ],
            temperature=0
        )
        direction = resp.choices[0].message.content.strip().title()
        print("LLM direction:", direction)
    except Exception as e:
        print(f"OpenAI failed ({e}); falling back to technical")

# 2) Fallback: simple SuperTrend rule
if not direction:
    # Fetch 15 days of daily bars for USD/JPY
    df = yf.download("JPY=X", period="15d", interval="1d", progress=False)
    # Compute SuperTrend(10,3)
    st = ta.supertrend(df["High"], df["Low"], df["Close"], length=10, multiplier=3.0)
    df = df.join(st)
    last = df.iloc[-1]
    close = last["Close"]
    sup = last["SUPERT_10_3.0"]
    # 0.1% buffer around the band
    if close > sup * 1.001:
        direction = "Long"
    elif close < sup * 0.999:
        direction = "Short"
    else:
        direction = "Neutral"
    print("Technical fallback direction:", direction)

# 3) Build JSON and write
payload = {
    "direction":     direction,
    "stop_loss":     0,
    "take_profit_1": 0,
    "take_profit_2": 0
}
with open("usdjpy.json", "w") as f:
    json.dump(payload, f, indent=2)
print("Wrote usdjpy.json:", payload)

#!/usr/bin/env python3
import os
import json
import openai

# 1) Load API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

# 2) Define multi-line prompt using triple quotes
PROMPT = """
SYSTEM: You are a professional FX analyst.

USER:
Provide today’s USD/JPY market outlook in JSON+text.
 A) Determine overall direction (Long/Short/Neutral) by combining:
    • Technical: ATR(14), support/resistance, trend.
    • Fundamental: Fed vs BoJ stance, U.S. macro, geo-political, and name any high-volatility report (NFP, CPI) or null.
 B) Calculate:
    • stop_loss just beyond nearest S/R pivot or ±1×ATR.
    • take_profit_1 at next pivot or ±0.5×ATR.
    • take_profit_2 at second pivot or ±1.5×ATR.
 C) Next 4–8 hrs: give bias or key level target.
 D) Summary: up to 5 sentences explaining today’s outlook and any caveat.

Respond ONLY with valid JSON exactly:
{
  "direction": "...",
  "stop_loss": 0,
  "take_profit_1": 0,
  "take_profit_2": 0,
  "high_volatility_report": "..." or null,
  "next_window": "...",
  "summary": "..."
}
NO extra text.
"""

# 3) Call OpenAI API
try:
    resp = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a professional FX analyst."},
            {"role": "user",   "content": PROMPT}
        ],
        temperature=0
    )
    content = resp.choices[0].message.content.strip()
    # Parse JSON from model response
    data = json.loads(content)
except Exception as e:
    print(f"OpenAI API error, defaulting to fallback: {e}")
    # Fallback default JSON structure
    data = {
        "direction": "Neutral",
        "stop_loss": 0,
        "take_profit_1": 0,
        "take_profit_2": 0,
        "high_volatility_report": None,
        "next_window": "",
        "summary": ""
    }

# 4) Write JSON to file
with open("usdjpy.json", "w") as f:
    json.dump(data, f, indent=2)

print("Wrote usdjpy.json:", data)

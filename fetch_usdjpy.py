#!/usr/bin/env python3
import os, json
import openai

# 1) Load API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

PROMPT = "Provide today’s USD/JPY market direction only: long, short, or neutral."

# 2) Try the API call; on any error, default to Neutral
try:
    resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": ""},
            {"role": "user",   "content": PROMPT}
        ],
        temperature=0
    )
    direction = resp.choices[0].message.content.strip().title()
except Exception as e:
    print(f"API call failed, defaulting to Neutral: {e}")
    direction = "Neutral"

# 3) Build and write JSON
payload = {
    "direction":     direction,
    "stop_loss":     0,
    "take_profit_1": 0,
    "take_profit_2": 0
}
with open("usdjpy.json", "w") as f:
    json.dump(payload, f, indent=2)

print("Wrote usdjpy.json:", payload)

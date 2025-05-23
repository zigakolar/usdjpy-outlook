#!/usr/bin/env python3
import os
import json
import openai

# 1) Load API key
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

PROMPT = "Provide today’s USD/JPY market direction only: long, short, or neutral."

# 2) v1.x SDK call
resp = openai.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": ""},
        {"role": "user",   "content": PROMPT}
    ],
    temperature=0
)

# 3) Extract and normalize
direction = resp.choices[0].message.content.strip().title()

# 4) Build your JSON payload
payload = {
    "direction":     direction,
    "stop_loss":     0,
    "take_profit_1": 0,
    "take_profit_2": 0
}

# 5) Write to file
with open("usdjpy.json", "w") as f:
    json.dump(payload, f, indent=2)

print("Wrote usdjpy.json:", payload)

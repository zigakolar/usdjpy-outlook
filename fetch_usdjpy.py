#!/usr/bin/env python3
import os, json
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")
PROMPT = "Provide today’s USD/JPY market direction only: long, short, or neutral."

# New v1 SDK call
resp = openai.chat.completions.create(
    model="gpt-4-turbo",
    messages=[
        {"role": "system", "content": ""},
        {"role": "user",   "content": PROMPT}
    ],
    temperature=0
)

direction = resp.choices[0].message.content.strip().title()

payload = {
    "direction":     direction,
    "stop_loss":     0,
    "take_profit_1": 0,
    "take_profit_2": 0
}

with open("usdjpy.json","w") as f:
    json.dump(payload, f, indent=2)

print("Wrote usdjpy.json:", payload)

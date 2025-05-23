#!/usr/bin/env python3
import os, json, openai

# 1) Configure
openai.api_key = os.getenv("OPENAI_API_KEY")
PROMPT = (
    "Provide today’s USD/JPY market direction only: long, short, or neutral."
)

# 2) Call OpenAI
resp = openai.ChatCompletion.create(
    model="gpt-4o-mini",
    messages=[{"role":"system","content":""},
              {"role":"user","content":PROMPT}],
    temperature=0
)
direction = resp.choices[0].message.content.strip().title()

# 3) Write JSON file
payload = {"direction": direction}
with open("usdjpy.json", "w") as f:
    json.dump(payload, f, indent=2)

print("Wrote usdjpy.json:", payload)

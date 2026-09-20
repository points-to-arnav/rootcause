import os
import time
from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
    default_headers={
        "HTTP-Referer": "https://github.com/points-to-arnav/rootcause",
        "X-Title": "AskData Analyst",
    }
)

# Free model on OpenRouter (fast mini tier)
model_name = "nex-agi/nex-n2.5-mini:free"

print(f"Sending request to OpenRouter ({model_name})...")
start_time = time.time()

try:
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are an expert data analysis query planner. Output JSON only."},
            {"role": "user", "content": "Translate to query plan: 'Show monthly revenue for 2026'"}
        ],
        temperature=0.1,
        max_tokens=512,
        timeout=30.0
    )
    elapsed = time.time() - start_time
    print(f"Response Time: {elapsed:.2f} seconds\n")
    print(completion.choices[0].message.content)
except Exception as e:
    elapsed = time.time() - start_time
    print(f"Failed after {elapsed:.2f} seconds:")
    print(e)

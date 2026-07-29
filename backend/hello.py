import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
)

print(response.choices[0].message.content)

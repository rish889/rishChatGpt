import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = 1.0
ALLOWED_MODELS = {"gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"}

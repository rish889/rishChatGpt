import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# timeout: max seconds to wait on a single HTTP call to OpenAI (connect + read).
# max_retries: the SDK's built-in retry count (exponential backoff) for connection
# errors, timeouts, and 429/5xx responses on that call. Doesn't cover a stream that
# fails partway through after already yielding content — callers handle that case.
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=60.0, max_retries=2)
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = 1.0
ALLOWED_MODELS = {"gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"}

# Dimensionality must match models.EMBEDDING_DIM.
EMBEDDING_MODEL = "text-embedding-3-small"

# USD per 1M tokens (input, output). Approximate, hand-maintained snapshot of OpenAI's
# public pricing for cost logging only — not billing-accurate, may drift over time.
MODEL_PRICING = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
}


def embed_texts(texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_price, output_price = MODEL_PRICING.get(model, (0.0, 0.0))
    return (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price

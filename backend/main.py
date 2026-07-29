import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": request.message}],
    )
    return ChatResponse(reply=response.choices[0].message.content)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def token_stream():
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": request.message}],
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return StreamingResponse(token_stream(), media_type="text/plain")

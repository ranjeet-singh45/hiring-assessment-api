from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .agent import handle_chat
from .catalog import catalog
from .retrieval import retriever

app = FastAPI(title="SHL Assessment Recommendation Agent")


@app.on_event("startup")
def _startup():
    catalog.load()
    retriever.build()


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str = ""


class ChatResponse(BaseModel):
    reply: str
    recommendations: list[Recommendation] = Field(default_factory=list)
    end_of_conversation: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not catalog.items:
        try:
            catalog.load()
            retriever.build()
        except Exception:
            pass
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    result = handle_chat(messages)
    recs = result.get("recommendations", [])[:10]
    return ChatResponse(
        reply=result["reply"],
        recommendations=[Recommendation(**r) for r in recs],
        end_of_conversation=bool(result.get("end_of_conversation", False)),
    )

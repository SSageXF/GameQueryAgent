from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Intent = Literal["knowledge", "advice", "chitchat", "out_of_scope"]
Status = Literal["answered", "partial_answer", "needs_clarification", "insufficient_evidence", "unsupported"]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=1000)
    history: list[Message] = Field(default_factory=list, max_length=24)

    @field_validator("message")
    @classmethod
    def nonempty(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("问题不能为空")
        return value

    @model_validator(mode="after")
    def history_budget(self):
        if sum(len(m.content) for m in self.history) > 24000:
            raise ValueError("历史上下文超过24000字，请清空或缩短对话")
        return self


class Source(BaseModel):
    id: str
    title: str
    source_title: str
    url: str
    collected_at: str
    version_scope: str
    claim_type: str = "rule"
    verification: str = "official_page_checked"
    official_url: str | None = None
    excerpt: str = ''
    excerpt_kind: Literal['quote', 'reference'] = 'quote'


class ChatResponse(BaseModel):
    answer: str
    intent: Intent
    status: Status
    sources: list[Source]
    retrieved_ids: list[str]
    latency_ms: float
    timings_ms: dict[str, float]
    mode: Literal["live", "mock"]
    model_used: bool
    request_id: str
    retrieval_plan: dict | None = None
    routing: dict | None = None
    model_calls: list[dict] = Field(default_factory=list)
    notice: str | None = None
    generation_error: str | None = None

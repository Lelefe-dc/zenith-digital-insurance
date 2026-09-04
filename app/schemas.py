from pydantic import BaseModel, Field


class ChatStartRequest(BaseModel):
    user_id: str | None = None
    channel: str = "web"


class ChatMessageRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=3000)


class Option(BaseModel):
    label: str
    value: str


class ChatResponse(BaseModel):
    session_id: str
    messages: list[str]
    options: list[Option] = []
    input_hint: str | None = None
    claim_reference: str | None = None
    allow_attachment: bool = False

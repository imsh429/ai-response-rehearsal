from typing import Literal
from pydantic import BaseModel, Field, model_validator

class SessionRequest(BaseModel):
    scenario_id: Literal['delivery', 'return', 'promise']

class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    @model_validator(mode='after')
    def not_blank(self):
        self.content=self.content.strip()
        if not self.content:
            raise ValueError('메시지를 입력하세요.')
        return self

class Evidence(BaseModel):
    source_id: str = Field(description='제공된 근거의 정확한 ID')
    quote: str = Field(min_length=1, description='해당 근거에서 그대로 복사한 짧은 인용')

class Criterion(BaseModel):
    key: Literal['facts', 'policy', 'solution', 'communication']
    score: int = Field(ge=0, le=25)
    reason: str
    evidence: list[Evidence] = Field(min_length=1, max_length=4)
    action: str

class Evaluation(BaseModel):
    summary: str
    criteria: list[Criterion] = Field(min_length=4, max_length=4)
    @model_validator(mode='after')
    def unique_keys(self):
        if {c.key for c in self.criteria} != {'facts','policy','solution','communication'}:
            raise ValueError('평가 항목은 중복 없이 네 가지여야 합니다.')
        return self

class Rewrite(BaseModel):
    message_id: str
    original: str
    improved: str
    reason: str

class Coaching(BaseModel):
    strengths: list[str] = Field(min_length=1, max_length=3)
    next_actions: list[str] = Field(min_length=1, max_length=3)
    rewrites: list[Rewrite] = Field(min_length=1, max_length=3)


class PolicySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=8)

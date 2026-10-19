from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    query: str = Field(min_length=1, max_length=720)
    max_results: int = Field(default=5, ge=1, le=8, strict=True)

class ResearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    target: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=600)
    max_results: int = Field(default=5, ge=1, le=8, strict=True)
    model: str = Field(default='', max_length=160)

class Source(BaseModel):
    id: int
    title: str
    url: str
    content: str
    published_date: str | None = None

class Timings(BaseModel):
    search_seconds: float = 0
    model_seconds: float = 0
    total_seconds: float = 0

class ResearchResponse(BaseModel):
    mode: Literal['demo', 'live']
    status: Literal['ok', 'partial', 'no_results']
    query: str
    answer: str
    sources: list[Source]
    citations: list[int]
    warnings: list[str]
    timings: Timings
    collected_at: str
    model: str

class SearchResponse(BaseModel):
    mode: Literal['demo', 'live']
    status: Literal['ok', 'no_results']
    query: str
    sources: list[Source]
    warnings: list[str]
    timings: Timings
    collected_at: str

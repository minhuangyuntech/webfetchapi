from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    query: str = Field(min_length=1, max_length=720)
    max_results: int = Field(default=5, ge=1, le=8, strict=True)
    include_body: bool = Field(default=True, strict=True)


class Source(BaseModel):
    id: int
    title: str
    url: str
    content: str  # Search snippet, retained for compatibility with v1 clients.
    published_date: str | None = None
    body_text: str | None = None
    extraction_status: Literal['not_requested', 'ok', 'failed'] = 'not_requested'
    extraction_error: str | None = None
    body_truncated: bool = False
    fetched_at: str | None = None


class Timings(BaseModel):
    search_seconds: float = 0
    extract_seconds: float = 0
    total_seconds: float = 0


class SearchResponse(BaseModel):
    mode: Literal['demo', 'live']
    status: Literal['ok', 'partial', 'no_results']
    query: str
    sources: list[Source]
    warnings: list[str]
    timings: Timings
    collected_at: str

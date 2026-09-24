"""
schemas.py
----------
Pydantic models for every endpoint. Length limits here are part of the
security story: they stop oversized payloads before any model runs.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

from backend.config import MAX_CODE_CHARS
from backend.utils.languages import strict_language


class AnalyzeRequest(BaseModel):
    language: str = Field(..., examples=["python"])
    code: str = Field(..., min_length=1, max_length=MAX_CODE_CHARS)
    error: str = Field(..., min_length=1, max_length=20_000)
    stack_trace: Optional[str] = Field("", max_length=20_000)
    expected_output: Optional[str] = Field(None, max_length=5_000)
    test_input: Optional[str] = Field(None, max_length=5_000)

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        return strict_language(v)


class SimilarBug(BaseModel):
    kb_id: str
    language: str
    bug_type: str
    error_pattern: str
    root_cause: str
    fix: str
    score: float


class ValidationResult(BaseModel):
    valid: Optional[bool]
    stage: str
    message: str
    line: Optional[int] = None


class ErrorLocation(BaseModel):
    line: int
    text: str
    reason: str
    source: str                  # ai | trace | syntax | diff
    sources: List[str] = []      # every signal that agreed on this line


class AnalyzeResponse(BaseModel):
    id: str
    language: str
    bug_type: str
    severity: str
    confidence: float
    root_cause: str
    explanation: str
    fix: str
    corrected_code: str
    error_locations: List[ErrorLocation] = []
    validation: ValidationResult
    similar_known_bugs: List[SimilarBug] = []
    retried: bool = False


class HistoryItem(AnalyzeResponse):
    original_code: str
    original_error: str
    created_at: str

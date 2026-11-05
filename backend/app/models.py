"""Pydantic schemas shared across API and pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Question(BaseModel):
    id: str
    type: Literal["mc", "tf"]
    question: str = Field(min_length=1)
    choices: list[str] = Field(min_length=2, max_length=4)
    correct: int = Field(ge=0, le=3)
    explanation: str = ""
    time: float = Field(ge=0)
    duration: float = Field(default=15.0, gt=0)

    @model_validator(mode="after")
    def check_correct_and_choices(self) -> Question:
        if self.type == "tf":
            self.choices = ["True", "False"]
        if self.correct >= len(self.choices):
            raise ValueError(
                f"correct index {self.correct} out of range for {len(self.choices)} choices"
            )
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("choices must be unique")
        return self


class QuestionsPayload(BaseModel):
    questions: list[Question]


class JobStatus(BaseModel):
    id: str
    stage: str
    error: str = ""
    title: str = ""
    language: str = "auto"
    duration: float = 0.0
    width: int = 0
    height: int = 0
    segments: int = 0
    question_count: int = 0

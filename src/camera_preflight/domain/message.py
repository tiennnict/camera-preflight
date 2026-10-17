"""Translatable message: a code plus parameters; text is resolved at render time."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    params: dict[str, Any] = {}

    def __hash__(self) -> int:
        return hash((self.code, tuple(sorted((k, str(v)) for k, v in self.params.items()))))

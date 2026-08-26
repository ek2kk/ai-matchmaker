from __future__ import annotations

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def get_col_spec(self, **_kw: object) -> str:
        return f"vector({self.dim})"

    def bind_processor(self, _dialect: object):
        def process(value: object) -> str | None:
            if value is None:
                return None
            if not isinstance(value, (list, tuple)):
                raise TypeError("embedding must be a sequence of floats")
            return "[" + ",".join(str(float(item)) for item in value) + "]"

        return process

    def result_processor(self, _dialect: object, _coltype: object):
        def process(value: object) -> list[float] | None:
            if value is None:
                return None
            if isinstance(value, list):
                return [float(item) for item in value]
            text = str(value).strip()
            if text.startswith("[") and text.endswith("]"):
                text = text[1:-1]
            if not text:
                return []
            return [float(part) for part in text.split(",")]

        return process

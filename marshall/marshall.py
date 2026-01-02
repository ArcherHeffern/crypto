from abc import ABC
from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass, is_dataclass, fields
from itertools import islice
from json import dumps as json_dumps, loads as json_loads
from typing import Any, Generic, Optional, TypeVar

TBase = TypeVar("TBase")


class DataclassMarshaller(Generic[TBase]):
    TAG = "__tag"

    def __init__(self) -> None:
        # tag -> class
        self._types: dict[str, type] = {}
        # class -> tag
        self._tags: dict[type, str] = {}

    def register(self, tag: str, cls: type) -> None:
        if tag in self._types and self._types[tag] is not cls:
            raise ValueError(
                f"Duplicate tag {tag!r} for {cls!r} and {self._types[tag]!r}"
            )
        if cls in self._tags and self._tags[cls] != tag:
            raise ValueError(
                f"Class {cls!r} registered with multiple tags: {self._tags[cls]!r}, {tag!r}"
            )
        self._types[tag] = cls
        self._tags[cls] = tag

    # ---------- Public API ----------

    def dumps(self, obj: TBase) -> str:
        return json_dumps(self._encode_value(obj))

    def loads(self, s: str) -> Optional[TBase]:
        raw = json_loads(s)
        out = self._decode_value(raw)
        return out  # type: ignore[return-value]

    def dump_stream(self, obj: TBase, writer: StreamWriter) -> None:
        writer.write((self.dumps(obj) + "\n").encode())

    async def load_stream(self, reader: StreamReader) -> Optional[TBase]:
        b = await reader.readuntil(b"\n")
        return self.loads(b.decode())

    # ---------- Recursive encoding/decoding ----------

    def _encode_value(self, v: Any) -> Any:
        # primitives
        if v is None or isinstance(v, (bool, int, float, str)):
            return v

        # sequences / mappings
        if isinstance(v, list):
            return [self._encode_value(x) for x in v]
        if isinstance(v, tuple):
            return [
                self._encode_value(x) for x in v
            ]  # JSON has no tuple; encode as list
        if isinstance(v, dict):
            # JSON object keys must be strings
            return {str(k): self._encode_value(val) for k, val in v.items()}

        # registered message/dataclass types
        cls = v.__class__
        tag = self._tags.get(cls)
        if tag is not None:
            payload = (
                self._dataclass_to_dict_recursive(v)
                if is_dataclass(v)
                else self._object_to_dict(v)
            )
            if self.TAG in payload:
                raise ValueError(f"Payload already contains reserved key '{self.TAG}'")
            return {self.TAG: tag, **payload}

        # plain dataclasses (not registered): encode structurally
        if is_dataclass(v):
            return self._dataclass_to_dict_recursive(v)

        raise TypeError(f"Not JSON-serializable: {v!r} (type={type(v)})")

    def _decode_value(self, v: Any) -> Any:
        if v is None or isinstance(v, (bool, int, float, str)):
            return v

        if isinstance(v, list):
            return [self._decode_value(x) for x in v]

        if isinstance(v, dict):
            # If it looks like a tagged object, decode it as one.
            tag = v.get(self.TAG)
            if isinstance(tag, str) and tag in self._types:
                cls = self._types[tag]
                payload = {
                    k: self._decode_value(val) for k, val in v.items() if k != self.TAG
                }
                return cls(**payload)

            # Otherwise it's just a normal dict of values
            return {k: self._decode_value(val) for k, val in v.items()}

        # Shouldn’t happen from json_loads, but kept for completeness
        return v

    def _dataclass_to_dict_recursive(self, dc: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(dc):
            out[f.name] = self._encode_value(getattr(dc, f.name))
        return out

    def _object_to_dict(self, obj: Any) -> dict[str, Any]:
        # Fallback for non-dataclass registered types (rare).
        # You can delete this if everything is a dataclass.
        if hasattr(obj, "__dict__"):
            return {k: self._encode_value(v) for k, v in obj.__dict__.items()}
        raise TypeError(
            f"Registered type {type(obj)} is not a dataclass and has no __dict__"
        )


@dataclass
class ABS(ABC): ...


@dataclass
class A(ABS):
    a: int
    b: list[B]


@dataclass
class B:
    c: list[dict[int, C]]
    d: C


@dataclass
class C:
    e: Optional[int]


@dataclass
class D:
    f: int


if __name__ == "__main__":
    c1 = C(5)
    c2 = C(None)
    c3 = C(6)
    b = B([{1: c1, 2: c2}, {1: c3}], c3)
    a = A(1, [b])
    d = D(10)

    objects = [a, b, c1, c2, c3, d]
    m = DataclassMarshaller[ABS]()
    m.register("a", A)
    m.register("b", B)
    m.register("c", C)
    m.register("d", D)
    for o in islice(objects, 1):
        j = m.dumps(o)
        fr = m.loads(j)
        if fr is None:
            print("fr is None")
            continue
        match fr:
            case A():
                print(fr.a, fr.b)
            case B():
                print(fr.c)
            case C():
                print(fr.e)
            case D():
                print(fr.f)
            case _:
                raise NotImplementedError(f"type {type(fr)} is not supported")
        print(fr)

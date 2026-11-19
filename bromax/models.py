from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Tick:
    symbol: str
    sequence: int
    stream_generation: int
    source_epoch: int
    received_at: str
    raw_quote: str
    normalized_quote: str
    pip_size: int
    digit: int
    provider_id: str | None = None
    quality: str = "VALID"

    def as_dict(self):
        return asdict(self)

def normalize_quote(quote: Any, pip_size: int) -> tuple[str, int]:
    if not isinstance(pip_size, int) or not 0 <= pip_size <= 12:
        raise ValueError("Invalid pip_size; expected integer precision 0..12")
    try:
        value = Decimal(str(quote))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Invalid quote: {quote!r}")
    if not value.is_finite() or value < 0:
        raise ValueError("Quote must be a finite non-negative number")
    quantum = Decimal(1).scaleb(-pip_size)
    quantized = value.quantize(quantum)
    # Reject values that would need rounding: quote precision must be consistent.
    if quantized != value:
        raise ValueError("Quote has more decimal places than supplied pip_size")
    fixed = f"{quantized:.{pip_size}f}"
    digit = int(fixed[-1]) if pip_size else int(fixed[-1])
    return fixed, digit

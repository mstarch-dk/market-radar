"""An ISIN (ISO 6166) checked by its shape and its check digit, so a mistyped code fails where it is written down,
not as a fund that is silently missing from SKAT's positive list."""
from __future__ import annotations

import re

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def valid(isin: object) -> bool:
    """True for a well-formed ISIN whose check digit adds up (Luhn over the letters-as-numbers expansion)."""
    if not isinstance(isin, str) or not ISIN_RE.match(isin):
        return False
    digits = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(isin[-1])

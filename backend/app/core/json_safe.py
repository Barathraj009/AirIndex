"""JSON-safe record serialization for observation rows.

PostgreSQL stores `double precision` NaN and we seed from pandas frames
that carry NaN for missing fares (INVALID/UNAVAILABLE observations). The
Python float->JSON path rejects non-finite floats
(`Out of range float values are not JSON compliant`), which made
`GET /api/fares` return 500. NULL is the semantically-correct
representation of "no fare", so non-finite floats are normalized to
None at every write boundary (seed and ingestion inserts).
"""

import math
from collections.abc import Mapping


def json_safe_float(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def records_json_safe(rows):
    """Return a new list of dicts with non-finite floats replaced by None."""
    out = []
    for row in rows:
        if isinstance(row, Mapping):
            out.append({k: json_safe_float(v) for k, v in row.items()})
        else:
            out.append(row)
    return out
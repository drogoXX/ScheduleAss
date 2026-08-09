"""
JSON serialization for parsed schedule payloads.

Parsed schedules come straight from a pandas DataFrame, so they contain
``pd.Timestamp``, ``NaT``, ``NaN`` and numpy scalar types that the stdlib JSON
encoder cannot handle. Naively coercing everything to ``str`` would break the
analysis layer, which does real datetime arithmetic on ``Start``/``Finish``.

These helpers record which columns held datetimes and restore them on load, so
a payload round-trips through the database with its dtypes intact.
"""

import json
import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

# Columns that must be restored to pandas datetimes when loading.
DATETIME_FIELDS = ("Start", "Finish", "Actual Start", "Actual Finish",
                   "Early Start", "Early Finish", "Late Start", "Late Finish",
                   "Baseline Start", "Baseline Finish")

_DATETIME_FIELDS_KEY = "_datetime_fields"


def _to_jsonable(value: Any) -> Any:
    """Convert a single pandas/numpy value into something JSON can encode."""
    # Missing values of every flavour collapse to null.
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        return value.isoformat()

    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        as_float = float(value)
        return None if math.isnan(as_float) or math.isinf(as_float) else as_float
    if isinstance(value, np.ndarray):
        return [_to_jsonable(v) for v in value.tolist()]

    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]

    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value

    # pandas scalar NA types (pd.NA) and anything else unrecognised.
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


class ScheduleJSONEncoder(json.JSONEncoder):
    """Encoder that understands pandas and numpy scalars."""

    def default(self, o: Any) -> Any:  # noqa: D102
        return _to_jsonable(o)


def dumps(payload: Any) -> str:
    """Serialize a schedule/analysis payload to a JSON string."""
    return json.dumps(_to_jsonable(payload), cls=ScheduleJSONEncoder, allow_nan=False)


def dumps_schedule_data(schedule_data: dict) -> str:
    """
    Serialize parsed schedule data, recording which activity fields were
    datetimes so ``loads_schedule_data`` can restore them.
    """
    payload = dict(schedule_data)
    activities = payload.get("activities") or []

    datetime_fields = set()
    for row in activities:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            if isinstance(value, (pd.Timestamp, datetime)) or value is pd.NaT:
                datetime_fields.add(key)

    # Always include the canonical date columns that are present, so a column
    # that is entirely NaT is still restored as a datetime column.
    for field in DATETIME_FIELDS:
        if activities and isinstance(activities[0], dict) and field in activities[0]:
            datetime_fields.add(field)

    payload[_DATETIME_FIELDS_KEY] = sorted(datetime_fields)
    return dumps(payload)


def loads_schedule_data(raw: str) -> dict:
    """Deserialize schedule data, restoring datetime fields to pd.Timestamp."""
    payload = json.loads(raw)
    datetime_fields = payload.pop(_DATETIME_FIELDS_KEY, list(DATETIME_FIELDS))

    activities = payload.get("activities")
    if activities and datetime_fields:
        for row in activities:
            if not isinstance(row, dict):
                continue
            for field in datetime_fields:
                if field in row:
                    row[field] = pd.to_datetime(row[field], errors="coerce")

    return payload


def loads(raw: str) -> Any:
    """Deserialize a generic JSON payload."""
    return json.loads(raw)

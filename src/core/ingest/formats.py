"""Detect which scheduling tool produced an uploaded export.

Detection is by column signature, not by filename, because both P6 and Microsoft
Project export plain `.csv` and users rename files freely.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Sequence

# Encodings tried in order. MS Project writes the ANSI codepage by default, so a
# strict UTF-8 read fails outright on any non-ASCII activity name.
CANDIDATE_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

# Columns that, taken together, only MS Project emits. `Total_Slack` and
# `Unique_ID` are the strongest signals; P6 uses "Total Float" and "Activity ID".
MSPROJECT_SIGNATURE = {"unique_id", "total_slack", "start_date", "finish_date"}
MSPROJECT_MIN_HITS = 3

# P6 exports always carry an activity identifier and a float column in this shape.
P6_SIGNATURE = {"activity id", "total float", "activity status", "activity name"}
P6_MIN_HITS = 2


class SourceFormat(str, Enum):
    """The scheduling tool an export came from."""

    P6_CSV = "p6_csv"
    MSPROJECT_CSV = "msproject_csv"
    UNKNOWN = "unknown"


def decode_bytes(content: bytes) -> tuple[str, str]:
    """Decode file bytes, returning (text, encoding_used).

    Raises UnicodeDecodeError only if every candidate encoding fails, which in
    practice means the file is not text.
    """
    last_error: Optional[UnicodeDecodeError] = None
    for encoding in CANDIDATE_ENCODINGS:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error  # type: ignore[misc]


def _header_fields(content: bytes) -> List[str]:
    """Read the header row and return normalised field names."""
    try:
        text, _ = decode_bytes(content[:65536])
    except UnicodeDecodeError:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        # Strip a UTF-8 BOM that survived as a character, then split on comma or
        # semicolon - some locales export semicolon-delimited CSV.
        line = line.lstrip("﻿")
        delimiter = ";" if line.count(";") > line.count(",") else ","
        return [f.strip().strip('"').lower() for f in line.split(delimiter)]
    return []


def detect_format(content: bytes, file_name: str = "") -> SourceFormat:
    """Identify the source tool from an export's header row.

    `file_name` is accepted for symmetry and future use (e.g. .xer) but is
    deliberately not used to decide between the two CSV dialects.
    """
    fields = set(_header_fields(content))
    if not fields:
        return SourceFormat.UNKNOWN

    if len(fields & MSPROJECT_SIGNATURE) >= MSPROJECT_MIN_HITS:
        return SourceFormat.MSPROJECT_CSV

    if len(fields & P6_SIGNATURE) >= P6_MIN_HITS:
        return SourceFormat.P6_CSV

    # P6 exports sometimes carry unit suffixes, e.g. "total float(d)". Retry the
    # P6 signature against suffix-stripped names before giving up.
    stripped = {f.split("(")[0].strip() for f in fields}
    if len(stripped & P6_SIGNATURE) >= P6_MIN_HITS:
        return SourceFormat.P6_CSV

    return SourceFormat.UNKNOWN


def describe_format(fmt: SourceFormat) -> str:
    """Human-readable label for messages shown to the user."""
    return {
        SourceFormat.P6_CSV: "Primavera P6 CSV export",
        SourceFormat.MSPROJECT_CSV: "Microsoft Project CSV export",
        SourceFormat.UNKNOWN: "unrecognised format",
    }[fmt]

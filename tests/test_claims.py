"""
Guards against unsupported capability claims re-entering the product.

The application previously advertised "GAO Schedule Assessment Guide
compliance" in the UI and in generated client reports while implementing no GAO
check whatsoever. These tests fail if such a claim reappears in anything a user
or client sees.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Everything a user or client can read: application code, the pages, and the
# public README. Requirements documents and the archive are excluded - the PRD
# records unbuilt intent and carries an explicit status note.
USER_FACING = (
    [ROOT / "app.py", ROOT / "README.md"]
    + sorted((ROOT / "pages").glob("*.py"))
    + sorted((ROOT / "src").rglob("*.py"))
)


def test_no_gao_claims_in_user_facing_surfaces():
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in USER_FACING
        if "GAO" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "GAO is claimed in "
        f"{offenders}, but no GAO-specific assessment is implemented. "
        "Either implement the GAO Schedule Assessment Guide checks or remove "
        "the claim."
    )


def test_no_gao_implementation_is_silently_expected():
    """
    If GAO checks are ever implemented, this test should be updated
    deliberately - it documents that none exist today.
    """
    analyzer = (ROOT / "src" / "analysis" / "dcma_analyzer.py").read_text(
        encoding="utf-8")
    assert "def _analyze_gao" not in analyzer


def test_health_score_weighting_is_documented_where_it_is_defined():
    """The weights must not drift back into undocumented inline literals."""
    module = (ROOT / "src" / "analysis" / "health_score.py").read_text(
        encoding="utf-8")
    for expected in ("COMPONENTS", "weight", "target", "zero_at"):
        assert expected in module

    calculator = (ROOT / "src" / "analysis" / "metrics_calculator.py").read_text(
        encoding="utf-8")
    assert "health_score.calculate" in calculator, \
        "metrics_calculator should delegate scoring, not inline its own weights"


def test_no_working_credentials_are_published():
    """Documented demo passwords were a live credential leak."""
    documents = [p for p in ROOT.glob("*.md")] + [ROOT / "app.py"]
    offenders = []
    for path in documents:
        text = path.read_text(encoding="utf-8")
        for secret in ("admin123", "viewer123"):
            if secret in text:
                # A historical note explaining the removal is acceptable.
                for line in text.splitlines():
                    if secret in line and not line.lstrip().startswith(">"):
                        offenders.append(f"{path.name}: {line.strip()[:60]}")
    assert not offenders, offenders

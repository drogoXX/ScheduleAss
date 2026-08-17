"""
Escaping of untrusted content in HTML rendering paths.

Issue and recommendation text is derived from uploaded CSV files, and the UI
renders it with unsafe_allow_html=True. Anything interpolated into that markup
must be escaped.
"""

import pytest

from src.utils.helpers import display_status_badge, esc


class TestEscaping:
    @pytest.mark.parametrize("payload", [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        '"><script>alert(1)</script>',
        "</div><script>alert(1)</script><div>",
        "' onmouseover='alert(1)",
    ])
    def test_markup_is_neutralised(self, payload):
        result = esc(payload)
        assert "<script" not in result
        assert "<img" not in result
        assert "&lt;" in result or "&quot;" in result or "&#x27;" in result

    def test_quotes_are_escaped_for_attribute_contexts(self):
        assert '"' not in esc('say "hello"')
        assert "'" not in esc("it's")

    def test_plain_text_is_preserved(self):
        assert esc("Install Pipe Rack 12-A") == "Install Pipe Rack 12-A"

    def test_ampersands_are_escaped_once(self):
        assert esc("Design & Build") == "Design &amp; Build"

    def test_none_becomes_empty_string(self):
        assert esc(None) == ""

    def test_numbers_are_stringified(self):
        assert esc(42) == "42"


class TestStatusBadge:
    def test_badge_escapes_untrusted_status(self):
        badge = display_status_badge("<script>alert(1)</script>")
        assert "<script>" not in badge

    def test_unknown_status_gets_the_default_colour(self):
        # Colours come from the shared palette via a CSS class, so the neutral
        # variant is what an unrecognised status must fall back to.
        assert "status-neutral" in display_status_badge("something-unexpected")

    def test_known_status_gets_its_variant(self):
        assert "status-danger" in display_status_badge("fail")
        assert "status-success" in display_status_badge("pass")


class TestCardsRenderSafely:
    """
    The card helpers call into Streamlit, so they are exercised for escaping by
    checking the markup they build rather than by rendering.
    """

    def test_issue_card_escapes_activity_derived_text(self, monkeypatch):
        captured = {}

        import src.utils.helpers as helpers

        monkeypatch.setattr(helpers.st, "markdown",
                            lambda body, **kwargs: captured.setdefault("body", body))

        helpers.display_issue_card({
            "severity": "high",
            "title": "<script>alert('title')</script>",
            "description": "<img src=x onerror=alert(1)>",
            "recommendation": "</div><script>alert(2)</script>",
            "count": 3,
        })

        body = captured["body"]
        assert "<script>" not in body
        assert "<img src=x" not in body
        assert "&lt;script&gt;" in body

    def test_recommendation_card_escapes_untrusted_text(self, monkeypatch):
        captured = {}

        import src.utils.helpers as helpers

        monkeypatch.setattr(helpers.st, "markdown",
                            lambda body, **kwargs: captured.setdefault("body", body))

        helpers.display_recommendation_card({
            "priority": "high",
            "title": "<script>alert(1)</script>",
            "category": "<b>cat</b>",
            "description": "d",
            "recommendation": "r",
            "impact": "i",
            "effort": "e",
        }, 1)

        body = captured["body"]
        assert "<script>" not in body
        assert "<b>cat</b>" not in body

    def test_missing_fields_do_not_raise(self, monkeypatch):
        import src.utils.helpers as helpers

        monkeypatch.setattr(helpers.st, "markdown", lambda body, **kwargs: None)
        # Analyses written by older versions may lack fields entirely.
        helpers.display_issue_card({})
        helpers.display_recommendation_card({}, 1)


class TestHealthScoreDisplay:
    def test_non_numeric_score_does_not_raise(self, monkeypatch):
        import src.utils.helpers as helpers

        captured = {}
        monkeypatch.setattr(helpers.st, "markdown",
                            lambda body, **kwargs: captured.setdefault("body", body))

        helpers.display_health_score(None, "Unknown")
        assert "N/A" in captured["body"]

    def test_rating_is_escaped(self, monkeypatch):
        import src.utils.helpers as helpers

        captured = {}
        monkeypatch.setattr(helpers.st, "markdown",
                            lambda body, **kwargs: captured.setdefault("body", body))

        helpers.display_health_score(50.0, "<script>alert(1)</script>")
        assert "<script>" not in captured["body"]

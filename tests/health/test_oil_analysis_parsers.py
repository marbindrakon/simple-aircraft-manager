"""
Unit tests for health/oil_analysis_parsers.py

These are pure unit tests — no DB access needed.
"""
from unittest.mock import MagicMock, patch
from pathlib import Path

from health.oil_analysis_parsers import _parse_number, _parse_date, _detect_lab, _HEX_RE


# ---------------------------------------------------------------------------
# _parse_number tests — no mocking needed
# ---------------------------------------------------------------------------

class TestParseNumber:
    def test_integer_string(self):
        assert _parse_number('12') == 12.0

    def test_float_string(self):
        assert _parse_number('12.5') == 12.5

    def test_less_than_prefix(self):
        # '<5' → strips '<', returns 5.0
        result = _parse_number('<5')
        assert result == 5.0

    def test_greater_than_prefix(self):
        result = _parse_number('>10')
        assert result == 10.0

    def test_na_returns_none(self):
        assert _parse_number('N/A') is None
        assert _parse_number('n/a') is None

    def test_dash_returns_none(self):
        assert _parse_number('-') is None

    def test_empty_string_returns_none(self):
        assert _parse_number('') is None

    def test_none_input_returns_none(self):
        assert _parse_number(None) is None

    def test_less_than_zero_point_one_literal(self):
        # The literal string '<0.1' is handled as 0.0
        assert _parse_number('<0.1') == 0.0

    def test_non_numeric_returns_none(self):
        assert _parse_number('abc') is None

    def test_unknown_string_returns_none(self):
        assert _parse_number('unknown') is None

    def test_zero(self):
        assert _parse_number('0') == 0.0

    def test_large_number(self):
        assert _parse_number('12345.6') == 12345.6


# ---------------------------------------------------------------------------
# _parse_date tests — no mocking needed
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_standard_date(self):
        assert _parse_date('4/5/2024') == '2024-04-05'

    def test_zero_padded(self):
        assert _parse_date('12/31/2023') == '2023-12-31'

    def test_empty_returns_none(self):
        assert _parse_date('') is None

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_invalid_format_returns_none(self):
        assert _parse_date('2024-04-05') is None


# ---------------------------------------------------------------------------
# _detect_lab tests — pure string matching, no mocking needed
# ---------------------------------------------------------------------------

class TestDetectLab:
    def test_detects_blackstone(self):
        text = 'Report from blackstone-labs.com for N12345'
        assert _detect_lab(text) == 'blackstone'

    def test_detects_avlab_by_domain(self):
        text = 'Aviation Laboratories avlab.com report'
        assert _detect_lab(text) == 'avlab'

    def test_detects_avlab_by_name(self):
        text = 'AVIATION LABORATORIES oil analysis'
        assert _detect_lab(text) == 'avlab'

    def test_unknown_lab_returns_unknown(self):
        text = 'Some other lab report with no known identifier'
        assert _detect_lab(text) == 'unknown'

    def test_case_insensitive_blackstone(self):
        text = 'BLACKSTONE-LABS.COM'
        assert _detect_lab(text) == 'blackstone'


# ---------------------------------------------------------------------------
# _HEX_RE regex tests — tests the hex color code filter pattern
# ---------------------------------------------------------------------------

class TestHexRe:
    def test_hash_prefix_hex_matches(self):
        assert _HEX_RE.match('#FFF') is not None
        assert _HEX_RE.match('#00CC00') is not None
        assert _HEX_RE.match('#ABC123') is not None

    def test_decimal_number_does_not_match(self):
        # Plain digits like '854' must NOT match (no '#' prefix)
        assert _HEX_RE.match('854') is None
        assert _HEX_RE.match('123') is None
        assert _HEX_RE.match('FF') is None  # no '#'

    def test_hex_without_hash_does_not_match(self):
        assert _HEX_RE.match('ABCDEF') is None

    def test_too_long_hex_does_not_match(self):
        # Pattern allows 1-8 hex chars after '#'; 9 should not match
        assert _HEX_RE.match('#123456789') is None


# ---------------------------------------------------------------------------
# parse() dispatch tests — mock fitz.open to test lab detection + dispatch
# ---------------------------------------------------------------------------

class TestParseDispatch:
    def _make_mock_fitz(self, text_content):
        """Create a mock fitz module whose open() returns a document with given text."""
        mock_page = MagicMock()
        # get_text() with no args or 'text' returns text_content; 'words' returns []
        mock_page.get_text.side_effect = lambda mode='text', **kw: (
            text_content if mode != 'words' else []
        )
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.close = MagicMock()
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc
        return mock_fitz

    def test_unrecognized_lab_raises_value_error(self):
        """parse() with unrecognized lab text raises ValueError."""
        import sys
        import pytest as _pytest
        from health.oil_analysis_parsers import parse

        mock_fitz = self._make_mock_fitz('Random oil lab report with no known identifier')

        with patch.dict(sys.modules, {'fitz': mock_fitz}):
            with _pytest.raises(ValueError, match='Unrecognized'):
                parse(Path('/fake/report.pdf'))

    def test_blackstone_lab_detected_in_text(self):
        """_detect_lab correctly returns 'blackstone' for Blackstone text."""
        from health.oil_analysis_parsers import _detect_lab
        text = 'This is an oil analysis report from blackstone-labs.com'
        assert _detect_lab(text) == 'blackstone'

    def test_avlab_lab_detected_in_text(self):
        """_detect_lab correctly returns 'avlab' for AVLab text."""
        from health.oil_analysis_parsers import _detect_lab
        text = 'Aviation Laboratories analysis report avlab.com'
        assert _detect_lab(text) == 'avlab'

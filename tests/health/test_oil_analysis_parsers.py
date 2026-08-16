"""
Unit tests for health/oil_analysis_parsers.py

These are pure unit tests — no DB access needed.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from health.oil_analysis_parsers import _parse_number, _parse_date, _detect_lab, _HEX_RE, parse


FIXTURE_DIR = Path(__file__).resolve().parent.parent / 'fixtures' / 'oil_pdfs'


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
# parse() dispatch tests — mock _extract_text to test lab detection + dispatch
# ---------------------------------------------------------------------------

class TestParseDispatch:
    def test_unrecognized_lab_raises_value_error(self):
        """parse() with unrecognized lab text raises ValueError."""
        from health import oil_analysis_parsers as oap

        with patch.object(oap, '_extract_text',
                          return_value='Random oil lab report with no known identifier'):
            with pytest.raises(ValueError, match='Unrecognized'):
                oap.parse(Path('/fake/report.pdf'))

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


# ---------------------------------------------------------------------------
# Golden-fixture regression — parse anonymized PDFs and assert the result
# matches the checked-in JSON. Catches drift in pypdfium2 word extraction or
# in any of the lab-specific parser logic.
#
# Fixtures live in tests/fixtures/oil_pdfs/ and were produced by
# scripts/anonymize_oil_pdfs.py from private originals (see test-pdfs/,
# gitignored). To refresh after intentional parser changes:
#
#   python scripts/anonymize_oil_pdfs.py   # regenerate PDFs from originals
#   python -c "import json, sys; sys.path.insert(0, '.'); \
#              from pathlib import Path; from health.oil_analysis_parsers import parse; \
#              [open(p.with_suffix('.json'), 'w').write(json.dumps(parse(p), indent=2, sort_keys=True) + chr(10)) \
#               for p in sorted(Path('tests/fixtures/oil_pdfs').glob('*.pdf'))]"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('pdf_name', [
    'blackstone_2024-01-25.pdf',
    'blackstone_2020-01-09.pdf',
    'avlab_2024-01-25.pdf',
    'avlab_2024-03-29.pdf',
])
def test_golden_fixture(pdf_name):
    pdf_path = FIXTURE_DIR / pdf_name
    json_path = pdf_path.with_suffix('.json')
    assert pdf_path.exists(), f'fixture missing: {pdf_path}'
    assert json_path.exists(), f'golden missing: {json_path}'

    actual = parse(pdf_path)
    expected = json.loads(json_path.read_text())
    assert actual == expected, (
        f'\nParser output for {pdf_name} drifted from golden.\n'
        f'If the change is intentional, regenerate the goldens (see test docstring).'
    )

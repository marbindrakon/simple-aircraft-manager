"""
Deterministic lab-specific PDF parsers for oil analysis reports.

Supports Blackstone Laboratories and Aviation Laboratories (AVLab).

Public API:
    parse(pdf_path: Path) -> dict
        Returns a dict matching the oil analysis report schema (samples: [...]).
        Raises ValueError if the lab is unrecognized.
"""

import re
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Blackstone element row order (20 elements, top to bottom in the report)
_BLACKSTONE_ELEMENTS = [
    'aluminum', 'chromium', 'iron', 'copper', 'lead', 'tin',
    'molybdenum', 'nickel', 'manganese', 'silver', 'titanium',
    'potassium', 'boron', 'silicon', 'sodium', 'calcium',
    'magnesium', 'phosphorus', 'zinc', 'barium',
]

# Blackstone oil property rows: (label_word, output_key)
_BLACKSTONE_PROPS = [
    ('SUS',        'viscosity_sus_210f'),
    ('cSt',        'viscosity_cst_100c'),
    ('Flashpoint', 'flashpoint_f'),
    ('Fuel',       'fuel_percent'),
    ('Antifreeze', 'antifreeze_percent'),
    ('Water',      'water_percent'),
    ('Insolubles', 'insolubles_percent'),
    ('TBN',        'total_base_number'),
    ('TAN',        'total_acid_number'),
]

# AVLab element names → schema keys
_AVLAB_ELEMENT_MAP = {
    'Iron':      'iron',
    'Copper':    'copper',
    'Nickel':    'nickel',
    'Chromium':  'chromium',
    'Silver':    'silver',
    'Magnesium': 'magnesium',
    'Aluminum':  'aluminum',
    'Lead':      'lead',
    'Silicon':   'silicon',
    'Titanium':  'titanium',
    'Tin':       'tin',
    'Moly.':     'molybdenum',
}

_DATE_RE = re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$')
# Hex color codes from AVLab bar indicators always start with '#' (e.g. #FFF, #00CC00).
# Requiring '#' prevents filtering numeric values like '854' (3 hex-compatible digits).
_HEX_RE  = re.compile(r'^#[0-9A-Fa-f]{1,8}$')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(pdf_path: Path) -> dict:
    """Detect lab and dispatch. Raises ValueError if lab unrecognized."""
    text = _extract_text(pdf_path)
    lab = _detect_lab(text)
    if lab == 'blackstone':
        return _parse_blackstone(pdf_path)
    if lab == 'avlab':
        return _parse_avlab(pdf_path)
    raise ValueError(
        "Unrecognized oil analysis lab. Expected Blackstone (blackstone-labs.com) "
        "or AVLab (avlab.com / AVIATION LABORATORIES)."
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_text(pdf_path: Path) -> str:
    """Extract plain text from all PDF pages."""
    try:
        import fitz
    except ImportError:
        raise ValueError("The 'pymupdf' package is not installed (pip install pymupdf)")
    doc = fitz.open(str(pdf_path))
    parts = [page.get_text() for page in doc]
    doc.close()
    return '\n'.join(parts)


def _detect_lab(text: str) -> str:
    t = text.lower()
    if 'blackstone-labs.com' in t:
        return 'blackstone'
    if 'avlab.com' in t or 'aviation laboratories' in t:
        return 'avlab'
    return 'unknown'


def _parse_date(s: str) -> str | None:
    """Convert M/D/YYYY or MM/DD/YYYY → YYYY-MM-DD, or None."""
    if not s:
        return None
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s.strip())
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    return None


def _parse_number(s: str) -> float | None:
    """Parse numeric string, handling < / > prefixes, N/A, -, unknown."""
    if not s:
        return None
    s = s.strip()
    if not s or s.lower() in ('n/a', '-', 'unknown', '—', '<0.1'):
        # Handle the literal string "<0.1" as 0
        if s.lower() == '<0.1':
            return 0.0
        return None
    s_stripped = re.sub(r'^[<>]', '', s).strip()
    try:
        return float(s_stripped)
    except ValueError:
        return None


def _get_words(pdf_path: Path):
    """Return all words as (x0, y0, text) from all pages."""
    try:
        import fitz
    except ImportError:
        raise ValueError("pymupdf not installed")
    doc = fitz.open(str(pdf_path))
    words = []
    for page in doc:
        for w in page.get_text('words', sort=True):
            words.append((float(w[0]), float(w[1]), str(w[4])))
    doc.close()
    return words


def _make_by_y(words, bucket=6):
    """Group (x, text) pairs into y-buckets of `bucket` pixels."""
    by_y = defaultdict(list)
    for x, y, t in words:
        by_y[round(y / bucket) * bucket].append((x, t))
    return by_y


# ---------------------------------------------------------------------------
# Blackstone parser
# ---------------------------------------------------------------------------

def _parse_blackstone(pdf_path: Path) -> dict:
    words = _get_words(pdf_path)
    by_y  = _make_by_y(words)

    def find_label_y(label, x_max=120, y_lo=None, y_hi=None):
        """Find the y-bucket where `label` appears at x ≤ x_max."""
        for yb in sorted(by_y.keys()):
            if y_lo is not None and yb < y_lo:
                continue
            if y_hi is not None and yb > y_hi:
                break
            for x, t in by_y[yb]:
                if t == label and x <= x_max:
                    return yb
        return None

    # ---- Header fields (top of page, y < 200) ----
    lab_number = unit_id = report_date_raw = oil_type = None
    for yb in sorted(by_y.keys()):
        if yb > 200:
            break
        row   = sorted(by_y[yb])
        texts = [t for x, t in row]
        xs    = [x for x, t in row]
        for i, t in enumerate(texts):
            if t == 'NUMBER:' and i + 1 < len(texts):
                lab_number = texts[i + 1]
            # "UNIT ID:" — require the preceding word to be "ID" which follows "UNIT"
            if t == 'ID:' and xs[i] > 440 and i + 1 < len(texts) and i > 0 and texts[i - 1] == 'UNIT':
                unit_id = texts[i + 1]
            if t == 'DATE:' and xs[i] > 300 and i + 1 < len(texts):
                report_date_raw = texts[i + 1]
            if t == 'GRADE:' and i + 1 < len(texts):
                oil_type = ' '.join(texts[i + 1:])

    # ---- Comments (y ≈ 205–285, past the address block) ----
    comment_lines = []
    prev_yb = -999
    line_buf = []
    for yb in sorted(by_y.keys()):
        if yb < 204 or yb > 288:
            continue
        row_ws = sorted((x, t) for x, t in by_y[yb] if x > 50)
        if not row_ws:
            continue
        if yb - prev_yb > 12 and line_buf:
            comment_lines.append(' '.join(t for _, t in line_buf))
            line_buf = []
        line_buf.extend(row_ws)
        prev_yb = yb
    if line_buf:
        comment_lines.append(' '.join(t for _, t in line_buf))
    raw_comment = ' '.join(comment_lines)
    comments = re.sub(r'^[A-Z]+:\s*', '', raw_comment).strip() or None

    # ---- Locate UNIT/LOC AVERAGES and UNIVERSAL AVERAGES columns ----
    unit_loc_hdr_x = 228  # default fallback
    universal_hdr_x = 537
    for yb in sorted(by_y.keys()):
        if 295 <= yb <= 325:
            for x, t in by_y[yb]:
                if t == 'LOCATION' and 190 < x < 270:
                    unit_loc_hdr_x = x
                if t == 'UNIVERSAL' and x > 500:
                    universal_hdr_x = x

    # ---- Find sample dates and their x-positions ----
    date_entries = []
    for yb in sorted(by_y.keys()):
        if 308 <= yb <= 325:
            for x, t in by_y[yb]:
                if _DATE_RE.match(t):
                    date_entries.append((x, t))
    date_entries.sort()
    if not date_entries:
        raise ValueError("No sample dates found in Blackstone PDF")

    sample_xs    = [x for x, _ in date_entries]
    sample_dates = [_parse_date(t) for _, t in date_entries]
    n = len(sample_dates)

    # ---- Derive column skip zones from element data ----
    # Find a reference element row with all 8 columns to locate UNIT/LOC
    # and UNIVERSAL data x-positions precisely.
    def get_ref_col_xs():
        for elem_label in ('ALUMINUM', 'IRON', 'LEAD'):
            ly = find_label_y(elem_label, y_lo=340, y_hi=410)
            if ly is None:
                continue
            xs_found = set()
            for yb in by_y:
                if abs(yb - ly) <= 6:  # ±6 to avoid contamination from adjacent rows
                    for x, t in by_y[yb]:
                        if x > 130 and re.match(r'^\d+$', t):
                            xs_found.add(round(x))
            if len(xs_found) >= n + 2:
                return sorted(xs_found)
        return []

    ref_xs = get_ref_col_xs()

    if len(ref_xs) >= n + 2:
        unit_loc_data_x  = ref_xs[1]      # 2nd column = UNIT/LOC AVG
        universal_data_x = ref_xs[-1]     # last column = UNIVERSAL AVG
    else:
        # Fallback: estimate from header text positions
        unit_loc_data_x  = unit_loc_hdr_x + 30
        universal_data_x = universal_hdr_x + 30

    ULSKIP_LO   = unit_loc_data_x - 35
    ULSKIP_HI   = unit_loc_data_x + 35
    UNIVSKIP_LO = universal_data_x - 35

    # Use actual element data x-positions (not date x-positions) as column anchors.
    # Date positions have a ~35px left offset vs data positions and different inter-column
    # spacing for the first gap, causing systematic nearest-neighbor misassignments.
    sample_data_xs = [x for x in ref_xs
                      if not (ULSKIP_LO < x < ULSKIP_HI) and x < UNIVSKIP_LO]
    if len(sample_data_xs) != n:
        # Fallback to date positions if ref didn't yield the right count
        sample_data_xs = sample_xs

    def assign_col(vx):
        """Map x-position to sample column index (0=current), or None for skip columns."""
        if ULSKIP_LO < vx < ULSKIP_HI:
            return None
        if vx >= UNIVSKIP_LO:
            return None
        if not sample_data_xs:
            return None
        best = min(range(n), key=lambda i: abs(sample_data_xs[i] - vx))
        if abs(sample_data_xs[best] - vx) < 45:
            return best
        return None

    def extract_row(label_word, y_lo=None, y_hi=None, label_x_max=120,
                    skip_words=frozenset()):
        """
        Find a row by its label word, then collect non-skip values in a ±6 px
        y-band mapped to sample columns. Returns list of n strings (None if absent).
        Using ±6 prevents adjacent rows (12 px apart) from contaminating each other.
        """
        ly = find_label_y(label_word, x_max=label_x_max, y_lo=y_lo, y_hi=y_hi)
        if ly is None:
            return [None] * n

        vals = {}
        # Sort by distance from ly so the label's own row is processed first.
        for yb in sorted(by_y.keys(), key=lambda y: abs(y - ly)):
            if abs(yb - ly) > 6:
                break  # remaining keys are further away (sorted order)
            for x, t in by_y[yb]:
                if x <= 130 or t in skip_words:
                    continue
                ci = assign_col(x)
                if ci is not None and ci not in vals:
                    vals[ci] = t
        return [vals.get(i) for i in range(n)]

    # ---- Sample metadata rows ----
    # "MI/HR on Oil": "Oil" at x≈86, y≈290-300
    oil_hrs_row     = extract_row('Oil',   y_lo=287, y_hi=300, label_x_max=100)
    # "MI/HR on Unit": "Unit" at x≈86, y≈300-315
    eng_hrs_row     = extract_row('Unit',  y_lo=300, y_hi=315, label_x_max=100)
    # "Make Up Oil Added": "Added" at x≈97, y≈319-333
    oil_added_row   = extract_row('Added', y_lo=319, y_hi=333, label_x_max=110,
                                  skip_words=frozenset(['qts']))

    # ---- Element rows (y ≈ 335–585) ----
    elem_data = {}
    for elem in _BLACKSTONE_ELEMENTS:
        elem_data[elem] = extract_row(elem.upper(), y_lo=335, y_hi=585)

    # ---- Oil property rows (y ≈ 585–730) ----
    prop_data = {}
    for label_word, prop_key in _BLACKSTONE_PROPS:
        prop_data[prop_key] = extract_row(label_word, y_lo=585, y_hi=730)

    # ---- Assemble samples ----
    samples = []
    for ci in range(n):
        elems = {}
        for elem in _BLACKSTONE_ELEMENTS:
            v = _parse_number(elem_data[elem][ci])
            if v is not None:
                elems[elem] = v

        props = {}
        for _, pk in _BLACKSTONE_PROPS:
            v = _parse_number(prop_data[pk][ci])
            if v is not None:
                props[pk] = v

        samples.append({
            'sample_date':      sample_dates[ci],
            'analysis_date':    None,
            'oil_hours':        _parse_number(oil_hrs_row[ci]),
            'engine_hours':     _parse_number(eng_hrs_row[ci]),
            'oil_added_quarts': _parse_number(oil_added_row[ci]),
            'elements_ppm':     elems,
            'oil_properties':   props or None,
            'lab_comments':     comments if ci == 0 else None,
            'status':           None,
        })

    return {
        'lab':         'Blackstone',
        'lab_number':  lab_number,
        'tail_number': unit_id,
        'oil_type':    oil_type,
        'report_date': _parse_date(report_date_raw),
        'samples':     samples,
    }


# ---------------------------------------------------------------------------
# AVLab parser
# ---------------------------------------------------------------------------

def _parse_avlab(pdf_path: Path) -> dict:
    words = _get_words(pdf_path)
    by_y  = _make_by_y(words)

    # ---- Header: tail number, report date ----
    tail_number = report_date_raw = None
    for yb in sorted(by_y.keys()):
        if yb > 150:
            break
        row   = sorted(by_y[yb])
        texts = [t for x, t in row]
        xs    = [x for x, t in row]
        for i, t in enumerate(texts):
            # "Tail No.: N5516G"
            if t == 'No.:' and xs[i] > 290 and i + 1 < len(texts):
                tail_number = texts[i + 1]
            # Report date: "Date: 4/5/2024" at high x
            if t == 'Date:' and xs[i] > 440 and i + 1 < len(texts):
                report_date_raw = texts[i + 1]

    # ---- Find section header y-positions ----
    # Sections start with "CURRENT SAMPLE" or "PREVIOUS SAMPLE N" at x < 50
    section_ys = []  # (y_bucket, is_current)
    for yb in sorted(by_y.keys()):
        row_texts = [t for x, t in by_y[yb] if x < 50]
        if 'CURRENT' in row_texts:
            section_ys.append(yb)
        elif 'PREVIOUS' in row_texts:
            section_ys.append(yb)
    section_ys.sort()

    if not section_ys:
        raise ValueError("No section headers found in AVLab PDF")

    # ---- Parse each section ----
    samples = []
    for sec_idx, sec_y in enumerate(section_ys):
        next_y = section_ys[sec_idx + 1] if sec_idx + 1 < len(section_ys) else 9999

        def in_section(yb):
            return sec_y <= yb < next_y

        # -- Status --
        # Check SEE+COMMENT and ACTION before NORMAL: every section header row has
        # "Normal Elevated High" as the legend, so NORMAL would always match first.
        status = None
        sec_row = ' '.join(t.upper() for _, t in sorted(by_y.get(sec_y, [])))
        if 'SEE' in sec_row and 'COMMENT' in sec_row:
            status = 'monitor'
        elif 'ACTION' in sec_row:
            status = 'action_required'
        elif 'NORMAL' in sec_row:
            status = 'normal'

        # Helper: iterate actual by_y keys in [sec_y+lo_off, sec_y+hi_off) ∩ [sec_y, next_y)
        # This avoids the range(sec_y+N, ..., 6) alignment bug: if N is not a multiple
        # of 6, the generated y-values never match by_y bucket keys (all multiples of 6).
        def sec_keys(lo_off, hi_off):
            lo = sec_y + lo_off
            hi = min(sec_y + hi_off, next_y)
            return sorted(k for k in by_y if lo <= k < hi)

        # -- Sample date (x ≈ 111, y = sec_y+6..sec_y+36) --
        sample_date = None
        for yb in sec_keys(6, 36):
            for x, t in sorted(by_y.get(yb, [])):
                if x < 130 and _DATE_RE.match(t):
                    sample_date = _parse_date(t)
                    break
            if sample_date:
                break

        # -- Analysis date (same row as element names; "Analysis" + "Date:") --
        analysis_date = None
        for yb in sec_keys(12, 48):
            row = sorted(by_y.get(yb, []))
            texts = [t for _, t in row]
            if 'Analysis' in texts and 'Date:' in texts:
                idx = texts.index('Date:')
                if idx + 1 < len(texts):
                    analysis_date = _parse_date(texts[idx + 1])
                break

        # -- Element names row: y where "Iron" appears at x > 150 --
        elem_names_y = None
        for yb in sec_keys(12, 54):
            for x, t in by_y.get(yb, []):
                if t == 'Iron' and x > 150:
                    elem_names_y = yb
                    break
            if elem_names_y:
                break

        # -- Element value row: one row below element names --
        val_y = None
        if elem_names_y is not None:
            val_y = elem_names_y + 12

        # -- Extract element ppm values --
        elements_ppm = {}
        if elem_names_y is not None and val_y is not None:
            # Build element name → x mapping
            elem_name_xs = {}
            for x, t in sorted(by_y.get(elem_names_y, [])):
                if t in _AVLAB_ELEMENT_MAP and x > 150:
                    elem_name_xs[t] = x

            # Collect value tokens from exactly val_y, skipping hex codes/labels.
            # Using only val_y (not a range) prevents the averages row (val_y+12)
            # from contributing partial hex fragments like 'FF', 'F', '9', 'E9'.
            val_tokens = []
            for x, t in sorted(by_y.get(val_y, [])):
                if x <= 150:
                    continue
                if _HEX_RE.match(t):
                    continue
                if t.startswith('('):
                    continue
                val_tokens.append((x, t))

            # Match each element to the nearest value token by x-proximity
            for elem_name, elem_x in elem_name_xs.items():
                best_val = None
                best_dist = 35  # tolerance in px
                i = 0
                while i < len(val_tokens):
                    vx, vt = val_tokens[i]
                    # Handle "< 0.1" split across two tokens
                    if vt == '<' and i + 1 < len(val_tokens):
                        combined = f"<{val_tokens[i + 1][1]}"
                        dist = abs(vx - elem_x)
                        if dist < best_dist:
                            best_dist = dist
                            best_val = combined
                        i += 2
                        continue
                    dist = abs(vx - elem_x)
                    if dist < best_dist:
                        best_dist = dist
                        best_val = vt
                    i += 1

                if best_val:
                    key = _AVLAB_ELEMENT_MAP[elem_name]
                    v = _parse_number(best_val)
                    if v is not None:
                        elements_ppm[key] = v

        # -- Scalar filter/oil fields --
        # Helper: find value after a label within this section.
        # Offsets MUST be multiples of 6 so the range hits by_y bucket keys.
        def find_val(label, sec_min_offset=42, sec_max_offset=204, x_min=None):
            for yb in sec_keys(sec_min_offset, sec_max_offset):
                row = sorted(by_y.get(yb, []))
                texts = [t for _, t in row]
                xs_r  = [x for x, _ in row]
                for i, t in enumerate(texts):
                    if t == label and (x_min is None or xs_r[i] >= x_min):
                        # Value is next word to the right at x < 200
                        cands = [(xs_r[j], texts[j]) for j in range(i + 1, len(texts))
                                 if xs_r[j] > xs_r[i] + 3 and xs_r[j] < 200]
                        if cands:
                            return cands[0][1]
                        # Or first word on next y-bucket at x ≈ 111
                        for nxt in (yb + 6, yb + 12):
                            for vx, vt in sorted(by_y.get(nxt, [])):
                                if 95 <= vx <= 145 and re.match(r'^[\d<]', vt):
                                    return vt
            return None

        tsn_raw       = find_val('TSN/TSO:',   sec_min_offset=42,  sec_max_offset=120)
        oil_added_raw = find_val('Added:',    sec_min_offset=60,  sec_max_offset=174)
        fp_raw        = find_val('F):',       sec_min_offset=90,  sec_max_offset=222)
        h2o_raw       = find_val('(ppm):',    sec_min_offset=102, sec_max_offset=234)
        tan_raw       = find_val('No.:',      sec_min_offset=102, sec_max_offset=240)

        # Oil Hours: look for "Oil" then "Hours:" then value (labeled row)
        oil_hours_raw = None
        for yb in sec_keys(48, 162):
            row = sorted(by_y.get(yb, []))
            for i, (x, t) in enumerate(row):
                if t == 'Oil' and x < 80:
                    # Next should be "Hours:" then value
                    rest = row[i + 1:]
                    if rest and rest[0][1] == 'Hours:':
                        vals = [(vx, vt) for vx, vt in rest[1:] if vx < 200]
                        if vals:
                            oil_hours_raw = vals[0][1]
                        elif len(rest) >= 1:
                            # Check next line
                            for vx, vt in sorted(by_y.get(yb + 6, [])):
                                if 95 <= vx <= 145 and re.match(r'^[\d]', vt):
                                    oil_hours_raw = vt
                                    break
                    break
            if oil_hours_raw:
                break

        # -- Comments: after "Comments:" label --
        lab_comments = None
        for yb in sorted(by_y.keys()):
            if not in_section(yb):
                continue
            row = sorted(by_y.get(yb, []))
            for i, (x, t) in enumerate(row):
                if t == 'Comments:' and x < 50:
                    parts = []
                    for yb2 in sorted(by_y.keys()):
                        if not in_section(yb2):
                            continue
                        if yb2 < yb:
                            continue  # only collect rows from Comments: onwards
                        for x2, t2 in sorted(by_y.get(yb2, [])):
                            if yb2 == yb and x2 <= x + 15:
                                continue  # skip "Comments:" label
                            if x2 > 20:
                                parts.append(t2)
                    lab_comments = ' '.join(parts).strip() or None
                    break
            if lab_comments is not None:
                break

        # -- Oil properties --
        oil_props = {}
        fp_val = _parse_number(fp_raw)
        if fp_val is not None:
            oil_props['flashpoint_f'] = fp_val
        h2o_val = _parse_number(h2o_raw)
        if h2o_val is not None:
            # H2O reported in ppm; convert to percent
            oil_props['water_percent'] = h2o_val / 10000.0
        tan_val = _parse_number(tan_raw)
        if tan_val is not None:
            oil_props['total_acid_number'] = tan_val

        # Skip "unknown" engine/oil hours
        engine_hours = None
        if tsn_raw and tsn_raw.lower() != 'unknown':
            engine_hours = _parse_number(tsn_raw)
        oil_hours = None
        if oil_hours_raw and oil_hours_raw.lower() != 'unknown':
            oil_hours = _parse_number(oil_hours_raw)

        # Sample number
        sample_number = None
        for yb in sec_keys(12, 54):
            row = sorted(by_y.get(yb, []))
            for i, (x, t) in enumerate(row):
                if t == 'Number:' and x < 80:
                    cands = [(vx, vt) for vx, vt in row[i + 1:] if vx > x + 3 and vx < 150]
                    if cands:
                        sample_number = cands[0][1]
                    break
            if sample_number:
                break

        samples.append({
            'sample_date':      sample_date,
            'analysis_date':    analysis_date,
            'sample_number':    sample_number,
            'oil_hours':        oil_hours,
            'engine_hours':     engine_hours,
            'oil_added_quarts': _parse_number(oil_added_raw),
            'elements_ppm':     elements_ppm,
            'oil_properties':   oil_props or None,
            'lab_comments':     lab_comments,
            'status':           status,
        })

    return {
        'lab':         'AVLab',
        'lab_number':  None,
        'tail_number': tail_number,
        'oil_type':    None,
        'report_date': _parse_date(report_date_raw),
        'samples':     samples,
    }

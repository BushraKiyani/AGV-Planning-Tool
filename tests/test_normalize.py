import pytest

from agv_agent.schema.normalize import _parse_agilox_number, _parse_dimensions_mm


# ---------------------------------------------------------------------------
# _parse_agilox_number
# ---------------------------------------------------------------------------

class TestParseAgiloxNumber:
    # --- German thousands-separator (period + exactly 3 digits) ---

    def test_raw_token_1511(self):
        assert _parse_agilox_number("1.511") == 1511.0

    def test_raw_token_1862(self):
        assert _parse_agilox_number("1.862") == 1862.0

    def test_annotated_payload_1000kg(self):
        # "1.000 KG (2.205 lbs)" is how AGILOX writes 1000 kg
        assert _parse_agilox_number("1.000 KG (2.205 lbs)") == 1000.0

    def test_annotated_radius_2100mm(self):
        # "2.100 MM (82.7 in)" is how AGILOX writes 2100 mm
        assert _parse_agilox_number("2.100 MM (82.7 in)") == 2100.0

    def test_multi_group_thousands(self):
        # 10.000 = ten thousand
        assert _parse_agilox_number("10.000 KG") == 10000.0

    # --- Plain integers (no thousands separator needed for < 1000) ---

    def test_plain_int_810(self):
        assert _parse_agilox_number("810") == 810.0

    def test_plain_int_annotated(self):
        assert _parse_agilox_number("214 KG (472 lbs)") == 214.0

    def test_plain_int_620mm(self):
        assert _parse_agilox_number("620 MM (24.4 in)") == 620.0

    # --- Decimal values that must NOT be treated as thousands-sep ---
    # These have fewer than 3 decimal digits, so the fullmatch \d{1,3}\.\d{3}
    # does not fire and the value is returned as-is.

    def test_speed_decimal_1_5(self):
        # 1.5 m/s: only 1 decimal digit → not a German thousands-sep
        assert _parse_agilox_number("1.5") == 1.5

    def test_speed_decimal_annotated(self):
        assert _parse_agilox_number("1.5 m/s") == 1.5

    def test_two_decimal_digits(self):
        # 0.65 (a confidence score): 2 decimal digits → not thousands-sep
        assert _parse_agilox_number("0.65") == 0.65

    # --- Edge cases ---

    def test_na_sentinel_returns_none(self):
        assert _parse_agilox_number("NA") is None

    def test_empty_string_returns_none(self):
        assert _parse_agilox_number("") is None

    def test_none_returns_none(self):
        assert _parse_agilox_number(None) is None

    def test_no_digits_returns_none(self):
        assert _parse_agilox_number("kg mm lbs") is None

    def test_leading_zero_german(self):
        # "0.810" matches \d{1,3}\.\d{3} → treated as 810 mm (physically
        # 0.810 mm is implausible for an AGV; 810 mm is the correct reading)
        assert _parse_agilox_number("0.810") == 810.0


# ---------------------------------------------------------------------------
# _parse_dimensions_mm
# ---------------------------------------------------------------------------

class TestParseDimensionsMm:
    def test_agilox_german_with_inches(self):
        raw = "1.511 x 810 x 1.862 MM (59.5 x 31.9 x 73.3 in)"
        assert _parse_dimensions_mm(raw) == (1511.0, 810.0, 1862.0)

    def test_plain_integers(self):
        assert _parse_dimensions_mm("1500 x 800 x 1200 mm") == (1500.0, 800.0, 1200.0)

    def test_no_spaces_no_unit(self):
        assert _parse_dimensions_mm("1500x800x1200MM") == (1500.0, 800.0, 1200.0)

    def test_all_below_1000_no_sep(self):
        assert _parse_dimensions_mm("950 x 780 x 900 mm") == (950.0, 780.0, 900.0)

    def test_unicode_multiplication_sign(self):
        # × (U+00D7) should be treated the same as 'x'
        assert _parse_dimensions_mm("1500×800×1200 mm") == (1500.0, 800.0, 1200.0)

    def test_all_three_use_german_sep(self):
        assert _parse_dimensions_mm("1.200 x 1.000 x 2.000 mm") == (1200.0, 1000.0, 2000.0)

    def test_fewer_than_3_numbers_returns_none_triple(self):
        assert _parse_dimensions_mm("1500 x 800") == (None, None, None)

    def test_empty_string_returns_none_triple(self):
        assert _parse_dimensions_mm("") == (None, None, None)

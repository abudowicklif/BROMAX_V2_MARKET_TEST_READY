import pytest
from bromax.models import normalize_quote

def test_final_digit_respects_precision_and_trailing_zero():
    assert normalize_quote("123.450",3)==("123.450",0)
    assert normalize_quote("123.457",3)==("123.457",7)
    assert normalize_quote("100",0)==("100",0)

def test_rejects_precision_mismatch():
    with pytest.raises(ValueError):
        normalize_quote("1.2345",3)

def test_rejects_bad_quote():
    with pytest.raises(ValueError):
        normalize_quote("NaN",3)

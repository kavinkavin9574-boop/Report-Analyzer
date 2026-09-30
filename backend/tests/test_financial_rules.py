from app.rules.financial_validation import validate_invoice_totals, detect_line_item_issues
from app.rules.missing_data import find_missing_fields


def test_consistent_invoice_total_produces_no_anomaly():
    result = validate_invoice_totals(subtotal=1000, tax=180, discount=0, shipping=0, stated_total=1180)
    assert result.is_consistent is True
    assert result.anomalies == []
    assert result.expected_total == 1180


def test_incorrect_total_is_flagged():
    result = validate_invoice_totals(subtotal=1000, tax=180, discount=0, shipping=0, stated_total=1300)
    assert result.is_consistent is False
    assert len(result.anomalies) == 1
    assert "does not match" in result.anomalies[0]["title"]


def test_missing_data_when_subtotal_or_total_absent_is_not_an_anomaly():
    result = validate_invoice_totals(subtotal=None, tax=180, discount=0, shipping=0, stated_total=None)
    assert result.is_consistent is True
    assert result.anomalies == []


def test_negative_quantity_flagged():
    issues = detect_line_item_issues([{"description": "Widget", "quantity": -5, "unit_price": 10}])
    assert any("Negative quantity" in i["title"] for i in issues)


def test_duplicate_line_item_flagged():
    items = [
        {"description": "Consulting", "quantity": 10, "unit_price": 100},
        {"description": "Consulting", "quantity": 10, "unit_price": 100},
    ]
    issues = detect_line_item_issues(items)
    assert any("duplicate" in i["title"].lower() for i in issues)


def test_missing_required_invoice_fields_detected():
    extracted = {"invoice_number": "INV-1", "vendor": "Acme"}
    missing = find_missing_fields("invoice", extracted)
    missing_names = [m["field_name"] for m in missing]
    assert "Invoice date" in missing_names
    assert "Total" in missing_names
    assert "Invoice number" not in missing_names  # was provided


def test_no_missing_fields_when_all_present():
    extracted = {
        "invoice_number": "INV-1", "invoice_date": "2026-01-01", "vendor": "Acme",
        "customer": "Beta", "currency": "USD", "subtotal": 100, "tax": 10,
        "total": 110, "payment_terms": "Net 30",
    }
    assert find_missing_fields("invoice", extracted) == []

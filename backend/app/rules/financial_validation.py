"""
Deterministic arithmetic checks for invoices. This is intentionally plain
Python, not the LLM — money math must be exact and reproducible.
"""
from dataclasses import dataclass


@dataclass
class FinancialCheckResult:
    expected_total: float | None
    stated_total: float | None
    difference: float | None
    is_consistent: bool
    anomalies: list[dict]


def validate_invoice_totals(
    subtotal: float | None,
    tax: float | None,
    discount: float | None,
    shipping: float | None,
    stated_total: float | None,
    tolerance: float = 0.01,
) -> FinancialCheckResult:
    anomalies: list[dict] = []

    if subtotal is None or stated_total is None:
        return FinancialCheckResult(
            expected_total=None,
            stated_total=stated_total,
            difference=None,
            is_consistent=True,  # can't judge without enough data — don't fabricate an anomaly
            anomalies=[],
        )

    expected_total = subtotal + (tax or 0) - (discount or 0) + (shipping or 0)
    difference = round(stated_total - expected_total, 2)
    is_consistent = abs(difference) <= tolerance

    if not is_consistent:
        anomalies.append({
            "title": "Invoice total does not match calculated total",
            "severity": "high",
            "description": (
                f"Calculated total from subtotal/tax/discount/shipping is "
                f"{expected_total:.2f}, but the document states {stated_total:.2f} "
                f"(difference of {difference:.2f})."
            ),
            "detection_type": "rule",
            "confidence": 1.0,
        })

    return FinancialCheckResult(
        expected_total=round(expected_total, 2),
        stated_total=stated_total,
        difference=difference,
        is_consistent=is_consistent,
        anomalies=anomalies,
    )


def detect_line_item_issues(line_items: list[dict]) -> list[dict]:
    anomalies = []
    seen = set()

    for item in line_items:
        qty = item.get("quantity")
        price = item.get("unit_price")
        desc = (item.get("description") or "").strip().lower()

        if qty is not None and qty < 0:
            anomalies.append({
                "title": "Negative quantity on line item",
                "severity": "high",
                "description": f"Line item '{item.get('description')}' has a negative quantity ({qty}).",
                "detection_type": "rule",
                "confidence": 1.0,
            })

        if price is not None and price < 0:
            anomalies.append({
                "title": "Negative unit price on line item",
                "severity": "high",
                "description": f"Line item '{item.get('description')}' has a negative unit price ({price}).",
                "detection_type": "rule",
                "confidence": 1.0,
            })

        key = (desc, qty, price)
        if desc and key in seen:
            anomalies.append({
                "title": "Possible duplicate line item",
                "severity": "medium",
                "description": f"Line item '{item.get('description')}' appears more than once with identical quantity and price.",
                "detection_type": "rule",
                "confidence": 0.7,
            })
        seen.add(key)

    return anomalies

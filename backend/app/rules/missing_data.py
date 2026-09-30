"""
Required-field checklists per document type. Never guesses a value — only
flags what genuinely wasn't extracted.
"""

REQUIRED_FIELDS = {
    "invoice": [
        "invoice_number", "invoice_date", "vendor", "customer",
        "currency", "subtotal", "tax", "total", "payment_terms",
    ],
    "contract": [
        "parties", "effective_date", "expiration_date", "payment_terms",
        "termination_clauses", "signature_information",
    ],
    "financial_report": [
        "revenue", "expenses", "reporting_period",
    ],
    "compliance": [
        "regulation_references", "compliance_requirements", "responsible_party",
    ],
}

_FIELD_LABELS = {
    "invoice_number": "Invoice number",
    "invoice_date": "Invoice date",
    "vendor": "Vendor",
    "customer": "Customer",
    "currency": "Currency",
    "subtotal": "Subtotal",
    "tax": "Tax",
    "total": "Total",
    "payment_terms": "Payment terms",
    "parties": "Parties",
    "effective_date": "Effective date",
    "expiration_date": "Expiration/termination date",
    "termination_clauses": "Termination clause",
    "signature_information": "Signature information",
    "revenue": "Revenue",
    "expenses": "Expenses",
    "reporting_period": "Reporting period",
    "regulation_references": "Regulation references",
    "compliance_requirements": "Compliance requirements",
    "responsible_party": "Responsible party",
}


def find_missing_fields(document_type: str, extracted: dict) -> list[dict]:
    required = REQUIRED_FIELDS.get(document_type, [])
    missing = []
    for field in required:
        value = extracted.get(field)
        is_empty = value is None or value == "" or value == [] or value == {}
        if is_empty:
            missing.append({
                "field_name": _FIELD_LABELS.get(field, field),
                "description": f"{_FIELD_LABELS.get(field, field)} was not detected in the document.",
            })
    return missing

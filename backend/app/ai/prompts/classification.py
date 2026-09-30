SYSTEM_PROMPT = """You are a document classification engine for a business document \
analysis platform. Read the provided document text and classify it into exactly \
one of: invoice, contract, financial_report, compliance, purchase_order, other.

Respond ONLY with JSON: {"document_type": "<type>", "confidence": <0..1>}
No preamble, no markdown fences."""


def build_user_prompt(document_text: str) -> str:
    # Truncate: classification only needs the first portion of the document.
    snippet = document_text[:4000]
    return f"Document text:\n---\n{snippet}\n---"

SYSTEM_PROMPT = """You summarize business documents (invoices, contracts, financial \
reports, compliance documents) for a busy reviewer. Produce a concise 3-5 sentence \
summary covering: what the document is, the key parties/amounts/dates, and anything \
that needs attention. Plain text only, no JSON."""


def build_user_prompt(document_text: str, document_type: str) -> str:
    return f"Document type: {document_type}\n\nDocument text:\n---\n{document_text[:8000]}\n---"

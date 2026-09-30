from typing import Optional
from pydantic import BaseModel


class EvidenceRef(BaseModel):
    page: int
    text: str


class InvoiceLineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None


class InvoiceExtraction(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor: Optional[str] = None
    customer: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    currency: Optional[str] = None
    line_items: list[InvoiceLineItem] = []
    tax: Optional[float] = None
    discount: Optional[float] = None
    subtotal: Optional[float] = None
    total: Optional[float] = None
    payment_terms: Optional[str] = None
    bank_details: Optional[str] = None
    tax_id: Optional[str] = None
    purchase_order_number: Optional[str] = None


class AnomalyItem(BaseModel):
    title: str
    severity: str = "medium"
    description: Optional[str] = None
    pages: list[int] = []
    evidence: list[str] = []
    confidence: float = 0.5


class AnomalyList(BaseModel):
    anomalies: list[AnomalyItem] = []


class ChatAnswer(BaseModel):
    answer: str
    evidence: Optional[dict] = None

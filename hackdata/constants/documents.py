# ═══════════════════════════════════════════════════════════════════
# documents.py — PDF options, caps, document template names
# ═══════════════════════════════════════════════════════════════════
# IMP: DOC_MAX_INVOICE_PDFS_PER_REQUEST enforces the 50-invoice cap
#      from TRD section 19 / CLAUDE.md Limits.

DOC_MAX_NARRATIVE_PER_RUN: int = 20
DOC_MAX_INVOICE_PDFS_PER_REQUEST: int = 50
DOC_DEFAULT_INVOICE_PICK_COUNT: int = 10
DOC_INVOICE_NUMBER_PATTERN: str = "INV-{order_id:06d}"
DOC_PDF_FORMAT: str = "A4"
DOC_PDF_TIMEOUT_SECONDS: float = 30.0
DOC_TEMPLATE_INVOICE: str = "invoice.html.j2"
DOC_TEMPLATE_STATEMENT: str = "statement.html.j2"

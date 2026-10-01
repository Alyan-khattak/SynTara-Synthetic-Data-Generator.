# ═══════════════════════════════════════════════════════════════════
# locales.py — locale codes and formats
# ═══════════════════════════════════════════════════════════════════
# IMP: named `locales` (plural) so it never clashes with stdlib `locale`.
# VERIFY: LOC_DEFAULT_TAX_RATE (GST), LOC_NATIONAL_ID_FAKE_MARKER.

LOC_DEFAULT_LOCALE: str = "en_PK"
LOC_DEFAULT_CURRENCY: str = "PKR"
LOC_CURRENCY_SYMBOLS: dict = {"PKR": "Rs", "USD": "$", "GBP": "£", "EUR": "€", "SAR": "﷼", "EGP": "E£"}
LOC_GROUPING_LAKH: str = "lakh"
LOC_GROUPING_WESTERN: str = "western"
LOC_DEFAULT_GROUPING: str = "lakh"                 # ASSUMED; most PKR displays use lakh
LOC_DOC_DATE_FORMAT: str = "%d/%m/%Y"
LOC_EXPORT_DATE_FORMAT: str = "%Y-%m-%d"
LOC_MOBILE_TEMPLATE: str = "+92 3{operator}{block1} {block2}"   # tokens defined in format_utils
LOC_MOBILE_DIGIT_COUNT: int = 10           # digits drawn per phone number (operator 2 + block1 4 + block2 4)
LOC_NATIONAL_ID_PATTERN: str = "#####-#######-#"
LOC_NATIONAL_ID_FAKE_MARKER: str = "0"             # VERIFY: real CNICs never start with 0
LOC_DEFAULT_TAX_LABEL: str = "Sales Tax (GST)"
LOC_DEFAULT_TAX_RATE: float = 0.18                 # VERIFY current GST rate

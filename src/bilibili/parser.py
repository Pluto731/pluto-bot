import re

BV_RE = re.compile(r'\bBV[a-zA-Z0-9]{10}\b')
URL_RE = re.compile(r'bilibili\.com/video/(BV[a-zA-Z0-9]{10})')
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

def extract_bv(text: str) -> str | None:
    url_m = URL_RE.search(text)
    if url_m:
        return url_m.group(1)
    bv_m = BV_RE.search(text)
    return bv_m.group() if bv_m else None

def extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group() if m else None

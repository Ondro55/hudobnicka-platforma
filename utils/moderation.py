# utils/moderation.py
import re
from typing import Dict, List

# pár základných vzorov (len na flag – žiadne auto-bany)
PATTERNS: List[re.Pattern] = [
    re.compile(r"\bfajka\b", re.IGNORECASE),
    re.compile(r"\boral\b|\borál\b", re.IGNORECASE),
    re.compile(r"\banal\b|\banál\b", re.IGNORECASE),
    re.compile(r"\bsex\b", re.IGNORECASE),
    re.compile(r"\bporno\b|\bxxx\b", re.IGNORECASE),
    re.compile(r"\bza\s+fajku\b|\bza\s+sex\b|\bza\s+oral\b|\bza\s+orál\b", re.IGNORECASE),
]

def auto_moderate_text(text: str) -> Dict[str, str]:
    """
    Jemná automatika: ak nájde nevhodný výraz, vráti {'flag': True, 'reason': 'nevhodny_obsah', 'note': '...'}.
    Nič neblokuje ani nebanne – len informácia pre manuálnu moderáciu.
    """
    t = (text or "").strip()
    if not t:
        return {"flag": False}

    hits = []
    for rx in PATTERNS:
        m = rx.search(t)
        if m:
            frag = m.group(0)
            if frag not in hits:
                hits.append(frag)

    if hits:
        return {"flag": True, "reason": "nevhodny_obsah", "note": "zachytené: " + ", ".join(hits[:5])}
    return {"flag": False}

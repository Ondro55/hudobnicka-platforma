# utils/moderation_text.py
import re
import unicodedata

LEET = str.maketrans({
    "0":"o","1":"i","3":"e","4":"a","5":"s","7":"t","@":"a","$":"s"
})

def _strip_diacritics(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )

def normalize(text: str):
    t = (text or "").lower()
    t = _strip_diacritics(t).translate(LEET)
    compact = re.sub(r"[^a-z0-9]+", "", t)
    words = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()
    return words, compact

# --- 1) Obchodovanie za sexuálnu službu (quid pro quo) ---
_VERBS   = r"(darujem|predam|predavam|vymenim|vymena|ponukam|ponuka|kupim|hladam)"
_TRANS   = r"(za|vymenou\s*za|na\s*vymenu\s*za)"
_SEXTERMS = r"(fajku|fajka|oral|oralyk?|oralny\s*sex|vyfajcit|vyfajci[ts]|vykourit|kourit|kouřit|oralkem?)"
NEG_EXCEPT = re.compile(r"\b(vodna\s*fajka|vodnu\s*fajku|dymka|tabak|shisha|sisha|vodnej\s*fajky)\b")

PAT_QPQ_1 = re.compile(rf"\b{_VERBS}\b[\s\S]{{0,120}}?\b{_TRANS}\b[\s\S]{{0,20}}?\b{_SEXTERMS}\b")
PAT_QPQ_2 = re.compile(rf"\b{_SEXTERMS}\b[\s\S]{{0,40}}?\b{_TRANS}\b[\s\S]{{0,120}}?\b")

# --- 2) „Nežiaducy sexuálny návrh“ (bez transakcie), najmä DM ---
PROP_TERMS = re.compile(r"\b(anal(ik)?|analny|sex(ik)?|pretiahnut|pretiahnes|pretiahni|vyfajc[ti]|vyfuk|vyfuknes|zasun|zasunes|vyhul[ia]t|vyhul)\b")

# --- 3) Deti (tvrdá stopka) ---
MINOR_TERMS = re.compile(r"\b(nezletil[ey]|maloleta?|14rocny|15rocny|16rocny|skolacka|skolacik|teenka|mladistv[ey])\b")

def check_text_categories(text: str):
    """Vráti zoznam zásahov: [{'category':..., 'severity':..., 'match':...}, ...]"""
    hits = []
    words, compact = normalize(text)

    # minors – hard stop
    if MINOR_TERMS.search(words):
        hits.append({"category":"sexual_minors", "severity":"critical", "match":"minors"})

    # sexual transaction
    if not NEG_EXCEPT.search(words):
        if PAT_QPQ_1.search(words) or PAT_QPQ_2.search(words) \
           or any(tok in compact for tok in ["zafajku","zaoral","zaoralyk"]):
            hits.append({"category":"sexual_transaction", "severity":"high", "match":"za-sex"})

    # sexual proposition (bez „za“)
    if PROP_TERMS.search(words):
        hits.append({"category":"sexual_proposition", "severity":"medium", "match":"prop-lexicon"})

    return hits

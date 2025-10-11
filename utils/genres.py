GENRE_CHOICES = [
  "Rock","Pop","Jazz","Blues","Metal","Folk","Country","Hip-hop","EDM","Klasika",
  "Funk","Soul","R&B","Reggae","World","Alternative","Indie","Punk","House","Techno",
  "Folklór"
]

FOLKLOR_SYNONYMS = {
  "folklor","folklór","ludove","ľudové","svadobne","svadobné",
  "svadobne ludovky","svadobné ľudovky","cimbalovka","dychovka"
}

def normalize_genre(label: str) -> str:
    s = (label or "").strip()
    if not s: return ""
    low = s.lower()
    if low in FOLKLOR_SYNONYMS: 
        return "Folklór"
    return s.title()

def join_csv(lst):
    seen, out = set(), []
    for x in lst:
        n = normalize_genre(x)
        if n and n not in seen:
            seen.add(n); out.append(n)
    return ",".join(out) if out else None

def split_csv(v: str):
    return [t.strip() for t in (v or "").split(",") if t.strip()]

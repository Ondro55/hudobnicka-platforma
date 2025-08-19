# modules/napln_mesta.py
import sys, os, csv
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, Mesto

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# heuristika na mapovanie stĺpcov
OBEC_KEYS  = ['nazov_obce','názov obce','nazov obce','obec','obec_nazov','obec (nazov)','obec_názov','názov_obce']
OKRES_KEYS = ['okres','nazov okresu','názov okresu','okres_nazov','okres (nazov)','okres_názov','názov_okresu']
KRAJ_KEYS  = ['kraj','nazov kraja','názov kraja','kraj_nazov','kraj (nazov)','samostatny kraj','vuc','samosprávny kraj','samospravny kraj']

def norm(s):
    return (s or '').strip()

def guess_columns(header_lower):
    """Vráti tuple (obec_col, okres_col, kraj_col) podľa názvov v hlavičke."""
    def find(keys):
        for k in keys:
            for h in header_lower:
                if k in h:
                    return h
        return None
    obec  = find(OBEC_KEYS)
    okres = find(OKRES_KEYS)
    kraj  = find(KRAJ_KEYS)
    return (obec, okres, kraj)

def open_csv(path):
    """Otvor CSV s detekciou oddeľovača a kódovania."""
    for enc in ('utf-8-sig','utf-8','cp1250','latin-1'):
        try:
            f = open(path, 'r', encoding=enc, newline='')
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;|\t')
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            return f, reader
        except Exception:
            try:
                f.close()
            except Exception:
                pass
            continue
    raise RuntimeError(f"Nepodarilo sa otvoriť CSV: {path}")

def collect_from_csv(path):
    added = set()
    f, reader = open_csv(path)
    with f:
        header = [h.strip() for h in (reader.fieldnames or [])]
        header_lower = [h.lower() for h in header]
        obec_col, okres_col, kraj_col = guess_columns(header_lower)

        # ak nevieme určiť stĺpce, skús common fallbacky
        if not obec_col:
            for cand in ('obec','nazov','názov'):
                if cand in header_lower: obec_col = cand; break
        if not okres_col:
            for cand in ('okres','nazov okresu','názov okresu'):
                if cand in header_lower: okres_col = cand; break
        if not kraj_col:
            for cand in ('kraj','nazov kraja','názov kraja','vuc'):
                if cand in header_lower: kraj_col = cand; break

        # mapovanie späť na pôvodné názvy (keďže máme lower)
        def orig_name(lower_name):
            if not lower_name: return None
            for h in header:
                if h.lower() == lower_name:
                    return h
            return None

        obec_col  = orig_name(obec_col)
        okres_col = orig_name(okres_col)
        kraj_col  = orig_name(kraj_col)

        if not obec_col:
            print(f"⚠️  {os.path.basename(path)}: neviem nájsť stĺpec pre OBEC. Preskakujem.")
            return added

        # iteruj riadky
        for row in reader:
            obec  = norm(row.get(obec_col))
            okres = norm(row.get(okres_col)) if okres_col else None
            kraj  = norm(row.get(kraj_col))  if kraj_col  else None
            if not obec:
                continue
            added.add((obec, okres or None, kraj or None))
    print(f"✓ {os.path.basename(path)} -> našiel som {len(added)} unikátnych obcí (kombinácia obec/okres/kraj).")
    return added

def napln_mesta():
    # 1) Nazbieraj VŠETKY CSV v ./data
    src_files = []
    if not os.path.isdir(DATA_DIR):
        print("❌ Adresár 'data/' neexistuje.")
        return

    for name in os.listdir(DATA_DIR):
        p = os.path.join(DATA_DIR, name)
        if os.path.isfile(p) and name.lower().endswith('.csv'):
            src_files.append(p)

    if not src_files:
        print("❌ Nenašiel som žiadne CSV v ./data (očakávam *.csv).")
        return

    print("📄 Načítam tieto CSV:")
    for x in src_files:
        print("  -", os.path.basename(x))

    # 2) Vyparsuj obce/okresy/kraje zo všetkých CSV
    all_items = set()
    for path in src_files:
        try:
            all_items |= collect_from_csv(path)
        except Exception as e:
            print(f"⚠️  Problém pri čítaní {os.path.basename(path)}: {e}")

    if not all_items:
        print("❌ Nenašiel som žiadne použiteľné riadky (obec/okres/kraj).")
        return

    # 3) Ulož do DB (doplň len nové kombinácie)
    with app.app_context():
        before = Mesto.query.count()
        existing = set((m.nazov or '', m.okres or None, m.kraj or None) for m in Mesto.query.all())
        to_add = []
        for (obec, okres, kraj) in all_items:
            if (obec, okres, kraj) not in existing:
                to_add.append(Mesto(nazov=obec, okres=okres, kraj=kraj))

        if to_add:
            db.session.bulk_save_objects(to_add)
            db.session.commit()

        after = Mesto.query.count()
        print(f"✅ Hotovo. Teraz {after} záznamov (pridaných {after - before}).")

if __name__ == "__main__":
    napln_mesta()

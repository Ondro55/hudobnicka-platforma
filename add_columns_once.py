import sqlite3, os, sys

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'muzikuj.db')
print("DB path:", db_path)
if not os.path.exists(db_path):
    print("❌ DB súbor neexistuje na očakávanom mieste. Skontroluj cestu v app.py.")
    sys.exit(1)

con = sqlite3.connect(db_path)
cur = con.cursor()

def has_col(table, col):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

added = []

# pridaj stĺpce len ak NAOZAJ chýbajú
if not has_col('pouzivatel', 'plan'):
    cur.execute("ALTER TABLE pouzivatel ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
    added.append('plan')

if not has_col('pouzivatel', 'account_type'):
    cur.execute("ALTER TABLE pouzivatel ADD COLUMN account_type TEXT NOT NULL DEFAULT 'individual'")
    added.append('account_type')

if not has_col('pouzivatel', 'searchable'):
    cur.execute("ALTER TABLE pouzivatel ADD COLUMN searchable INTEGER NOT NULL DEFAULT 0")
    added.append('searchable')

con.commit()
con.close()

print("Pridané stĺpce:", added if added else "nič (už existovali)")
print("✅ Hotovo. Teraz spusť:  python app.py")

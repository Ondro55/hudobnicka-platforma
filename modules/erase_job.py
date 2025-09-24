from datetime import datetime
from models import db, Pouzivatel

def anonymize_user(u: Pouzivatel):
    # minimalizácia osobných údajov
    stub = f"deleted_{u.id}"
    u.prezyvka = stub
    u.meno = None
    u.priezvisko = None
    u.email = f"{stub}@example.invalid"
    u.bio = None
    u.obec = None
    u.profil_fotka = None
    u.searchable = False
    u.aktivny = False
    u.is_deleted = True
    # voliteľne: zruš premium flagy, VIP a pod.
    u.is_vip = False

def run_erase_due(now_utc: datetime | None = None):
    now_utc = now_utc or datetime.utcnow()
    qs = (Pouzivatel.query
          .filter(Pouzivatel.erase_requested_at.isnot(None))
          .filter(Pouzivatel.erase_deadline_at.isnot(None))
          .filter(Pouzivatel.erase_deadline_at <= now_utc)
          .filter(Pouzivatel.is_deleted.is_(False)))
    count = 0
    for u in qs.all():
        anonymize_user(u)
        count += 1
    if count:
        db.session.commit()
    return count

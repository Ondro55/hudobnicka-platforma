# modules/napln_mesta.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

from models import db, Mesto

def napln_mesta():
    mesta = [
        "Bratislava", "Košice", "Prešov", "Žilina", "Nitra",
        "Trnava", "Banská Bystrica", "Trenčín", "Martin", "Poprad"
    ]

    with app.app_context():
        for nazov in mesta:
            existuje = Mesto.query.filter_by(nazov=nazov).first()
            if not existuje:
                db.session.add(Mesto(nazov=nazov))

        db.session.commit()
        print("✅ Mestá boli úspešne pridané.")

if __name__ == "__main__":
    napln_mesta()

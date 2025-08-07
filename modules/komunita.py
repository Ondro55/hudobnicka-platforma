from flask import Blueprint, render_template, request
from models import Pouzivatel

komunita_bp = Blueprint("komunita", __name__)

@komunita_bp.route("/komunita")
def komunita():
    meno_filter = request.args.get('hladaj_meno', '').strip().lower()
    nastroj_filter = request.args.get('nastroj', '').strip().lower()

    pouzivatelia_query = Pouzivatel.query

    if meno_filter:
        pouzivatelia_query = pouzivatelia_query.filter(Pouzivatel.prezyvka.ilike(f"%{meno_filter}%"))

    if nastroj_filter:
        pouzivatelia_query = pouzivatelia_query.filter(Pouzivatel.instrument.ilike(f"%{nastroj_filter}%"))

    pouzivatelia = pouzivatelia_query.all()

    komunita_data = []
    for pouzivatel in pouzivatelia:
        skupiny = [sk.nazov for sk in pouzivatel.skupina_clen]
        skupiny_text = ", ".join(skupiny) if skupiny else "Žiadna"

        komunita_data.append({
            'id': pouzivatel.id,
            'prezyvka': pouzivatel.prezyvka,
            'skupiny': skupiny_text,
            'nastroj': pouzivatel.instrument,
            'profil_fotka': pouzivatel.profil_fotka,
        })

    return render_template("komunita.html", uzivatelia=komunita_data)





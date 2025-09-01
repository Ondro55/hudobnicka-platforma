from flask import Blueprint, render_template, request
from sqlalchemy.orm import joinedload
from sqlalchemy import or_
from models import Pouzivatel

# ✅ Blueprint MUSÍ byť definovaný skôr, než použiješ @komunita_bp.route
komunita_bp = Blueprint("komunita", __name__)

@komunita_bp.route("/komunita", methods=["GET"])
def komunita():
    meno_filter = (request.args.get('hladaj_meno') or '').strip()
    nastroj_filter = (request.args.get('nastroj') or '').strip()

    q = (Pouzivatel.query
         .options(joinedload(Pouzivatel.skupina_clen))
         .order_by(Pouzivatel.prezyvka.asc()))

    if meno_filter:
        like = f"%{meno_filter}%"
        q = q.filter(or_(
            Pouzivatel.prezyvka.ilike(like),
            Pouzivatel.meno.ilike(like),
            Pouzivatel.priezvisko.ilike(like)
        ))

    if nastroj_filter:
        q = q.filter(Pouzivatel.instrument.ilike(f"%{nastroj_filter}%"))

    uzivatelia = q.all()
    return render_template("komunita.html", uzivatelia=uzivatelia)

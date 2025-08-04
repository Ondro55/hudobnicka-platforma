from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Udalost
from datetime import datetime, time, date

kalendar_bp = Blueprint('kalendar', __name__)

@kalendar_bp.route('/')
@login_required
def kalendar():
    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None

    if skupina:
        udalosti = skupina.udalosti
    else:
        udalosti = current_user.udalosti

    udalosti = sorted(udalosti, key=lambda x: x.datum)
    return render_template('modals/kalendar.html', udalosti=udalosti)

@kalendar_bp.route('/pridaj_ajax', methods=['POST'], endpoint='pridaj_ajax')
@login_required
def pridaj_udalost_ajax():
    data = request.get_json()
    udalost_id = data.get("id")  # ← tu berieme ID
    nazov = data.get("nazov")
    popis = data.get("popis")
    datum = data.get("datum")
    celodenne = data.get("celodenne") == 'true'
    miesto = data.get("miesto")

    if not nazov or not datum:
        return jsonify({"error": "Chýba názov alebo dátum."}), 400

    if celodenne:
        datum_cas = datetime.strptime(datum, "%Y-%m-%d")
    else:
        od = data.get("od")
        if not od:
            return jsonify({"error": "Chýba čas 'od'."}), 400
        datum_cas = datetime.strptime(f"{datum} {od}", "%Y-%m-%d %H:%M")

    skupina = current_user.skupina_clen[0] if current_user.skupina_clen else None

    # 🛠️ EDIT alebo NOVÁ?
    if udalost_id:
        udalost = Udalost.query.get(int(udalost_id))
        if not udalost:
            return jsonify({"error": "Udalosť sa nenašla."}), 404
    else:
        udalost = Udalost()
        db.session.add(udalost)

    # Spoločné nastavenia
    udalost.nazov = nazov
    udalost.popis = popis
    udalost.datum = datum_cas
    udalost.miesto = miesto
    udalost.celodenne = celodenne
    udalost.cas_od = datetime.strptime(data.get("od"), "%H:%M").time() if data.get("od") else None
    udalost.cas_do = datetime.strptime(data.get("do"), "%H:%M").time() if data.get("do") else None

    if skupina:
        udalost.skupina_id = skupina.id
        udalost.pouzivatel_id = None
    else:
        udalost.pouzivatel_id = current_user.id
        udalost.skupina_id = None

    db.session.commit()
    return jsonify({"message": "Udalosť uložená."})



@kalendar_bp.route('/udalosti')
def zoznam_udalosti():
    if not current_user.is_authenticated:
        return jsonify([])

    # Všetky udalosti používateľa alebo jeho skupín
    moje_skupiny = [s.id for s in current_user.skupina_clen]
    udalosti = Udalost.query.filter(
        (Udalost.pouzivatel_id == current_user.id) |
        (Udalost.skupina_id.in_(moje_skupiny))
    ).all()

    # ✅ Debug výpis do konzoly
    print(f"Používateľ: {current_user.id}, Skupiny: {moje_skupiny}")
    for u in udalosti:
        print(f"{u.id} | {u.nazov} | {u.datum} | používateľ: {u.pouzivatel_id} | skupina: {u.skupina_id}")

    # Výstup pre kalendár
    data = []
    for u in udalosti:
        is_all_day = (
            isinstance(u.datum, datetime)
            and u.datum.time() == time(0, 0)
        ) or (
            isinstance(u.datum, date) and not isinstance(u.datum, datetime)
        )

        data.append({
            'id': u.id,
            'title': u.nazov,
            'start': datetime.combine(u.datum, u.cas_od or time(0, 0)).isoformat(),
            'end': datetime.combine(u.datum, u.cas_do or (u.cas_od or time(0, 0))).isoformat(),
            'description': u.popis or '',
            'allDay': is_all_day,
            'extendedProps': {
                'miesto': u.miesto or ''
            }
        })

    return jsonify(data)


@kalendar_bp.route('/udalosti_v_dni/<datum>')
def udalosti_v_dni(datum):
    try:
        datum_obj = datetime.strptime(datum, "%Y-%m-%d").date()
    except ValueError:
        return jsonify([])

    if current_user.is_authenticated:
        udalosti = Udalost.query.filter(
            db.func.date(Udalost.datum) == datum_obj,
            ((Udalost.pouzivatel_id == current_user.id) |
             (Udalost.skupina_id.in_([s.id for s in current_user.skupina_clen])))
        ).all()
    else:
        udalosti = []

    vysledok = []
    for u in udalosti:
        vysledok.append({
            "id": u.id,
            "nazov": u.nazov,
            "miesto": u.miesto
        })

    return jsonify(vysledok)

@kalendar_bp.route('/zmaz/<int:udalost_id>', methods=['DELETE'])
@login_required
def zmaz_udalost(udalost_id):
    udalost = Udalost.query.get_or_404(udalost_id)
    
    # overenie, či má právo vymazať
    moje_skupiny = [s.id for s in current_user.skupina_clen]
    if (udalost.pouzivatel_id != current_user.id and
        udalost.skupina_id not in moje_skupiny):
        return jsonify({'error': 'Nemáš oprávnenie mazať túto udalosť.'}), 403

    db.session.delete(udalost)
    db.session.commit()
    return jsonify({'message': 'Udalosť zmazaná.'})

@kalendar_bp.route('/nacitaj_udalost/<int:udalost_id>')
@login_required
def nacitaj_udalost(udalost_id):
    udalost = Udalost.query.get_or_404(udalost_id)

    moje_skupiny = [s.id for s in current_user.skupina_clen]
    if (udalost.pouzivatel_id != current_user.id and
        udalost.skupina_id not in moje_skupiny):
        return jsonify({'error': 'Nemáš oprávnenie.'}), 403

    return jsonify({
        'id': udalost.id,
        'nazov': udalost.nazov,
        'popis': udalost.popis,
        'miesto': udalost.miesto,
        'datum': udalost.datum.strftime('%Y-%m-%d'),
        'cas_od': udalost.cas_od.strftime('%H:%M') if udalost.cas_od else '',
        'cas_do': udalost.cas_do.strftime('%H:%M') if udalost.cas_do else '',
        'celodenne': not udalost.cas_od and not udalost.cas_do
    })

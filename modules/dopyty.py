# modules/dopyty.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from models import db, Dopyt, Mesto
from datetime import datetime

dopyty = Blueprint('dopyty', __name__)

# ------------------------------------------------------------
# ZOZNAM DOPYTOV (len pre prihlásených) + jednoduché filtre
# ------------------------------------------------------------
@dopyty.route('/dopyty', methods=['GET'])
@login_required
def zobraz_dopyty():
    q = Dopyt.query

    typ_akcie = (request.args.get('typ_akcie') or '').strip()
    mesto_id  = request.args.get('mesto_id', type=int)
    datum_s   = (request.args.get('datum') or '').strip()

    if typ_akcie:
        q = q.filter(Dopyt.typ_akcie == typ_akcie)
    if mesto_id:
        q = q.filter(Dopyt.mesto_id == mesto_id)
    if datum_s:
        try:
            d = datetime.strptime(datum_s, "%Y-%m-%d").date()
            q = q.filter(Dopyt.datum == d)
        except ValueError:
            pass

    dopyty = q.order_by(Dopyt.datum.asc()).all()

    # do filtra na stránke dopytov posielame ORM objekty 'mesta'
    mesta = Mesto.query.order_by(Mesto.kraj, Mesto.okres, Mesto.nazov).all()
    return render_template('dopyty.html', dopyty=dopyty, mesta=mesta)


# ------------------------------------------------------------
# FORMULÁR NA PRIDANIE DOPYTU (GET)
#   -> pošleme 'zoznam_miest' (list dictov), presne ako chce šablóna
# ------------------------------------------------------------
@dopyty.route('/dopyty/pridat', methods=['GET'])
def formular_dopyt():
    # Ak je tabuľka prázdna v tej DB, ktorú práve používa appka,
    # doplníme základné mestá (jednorazovo).
    if Mesto.query.count() == 0:
        demo = [
            ("Bratislava",      "Bratislava I",    "Bratislavský kraj"),
            ("Košice",          "Košice I",        "Košický kraj"),
            ("Prešov",          "Prešov",          "Prešovský kraj"),
            ("Žilina",          "Žilina",          "Žilinský kraj"),
            ("Nitra",           "Nitra",           "Nitriansky kraj"),
            ("Trnava",          "Trnava",          "Trnavský kraj"),
            ("Banská Bystrica", "Banská Bystrica", "Banskobystrický kraj"),
            ("Trenčín",         "Trenčín",         "Trenčiansky kraj"),
            ("Martin",          "Martin",          "Žilinský kraj"),
            ("Poprad",          "Poprad",          "Prešovský kraj"),
        ]
        db.session.bulk_save_objects([Mesto(nazov=a, okres=b, kraj=c) for a, b, c in demo])
        db.session.commit()

    mesta = Mesto.query.order_by(Mesto.kraj, Mesto.okres, Mesto.nazov).all()
    return render_template('modals/dopyt_form.html', mesta=mesta)



# ------------------------------------------------------------
# PRIDANIE DOPYTU (POST)
#   endpoint name = 'pridaj_dopyt_post'  -> sedí so šablónou
# ------------------------------------------------------------
@dopyty.route('/pridaj_dopyt', methods=['POST'], endpoint='pridaj_dopyt_post')
def pridaj_dopyt():
    # honeypot proti spamu
    if (request.form.get('website') or '').strip():
        flash('Formulár bol zablokovaný (spam).', 'warning')
        return redirect(url_for('dopyty.zobraz_dopyty'))

    get = request.form.get

    typ_akcie = (get('typ_akcie') or '').strip()
    datum_s   = (get('datum') or '').strip()
    cas_od_s  = (get('cas_od') or '').strip()
    cas_do_s  = (get('cas_do') or '').strip()

    # mesto_id – bezpečné parsovanie na int
    mesto_id_raw = (get('mesto_id') or '').strip()
    mesto_id = int(mesto_id_raw) if mesto_id_raw.isdigit() else None
    mesto_obj = Mesto.query.get(mesto_id) if mesto_id else None

    rozpocet_s = (get('rozpocet') or '').strip().replace(',', '.')
    popis      = (get('popis') or '').strip()
    meno       = (get('meno') or '').strip()
    email      = (get('email') or '').strip()

    # konverzie
    datum  = datetime.strptime(datum_s, '%Y-%m-%d').date() if datum_s else None
    cas_od = datetime.strptime(cas_od_s, '%H:%M').time() if cas_od_s else None
    cas_do = datetime.strptime(cas_do_s, '%H:%M').time() if cas_do_s else None
    try:
        rozpocet = float(rozpocet_s) if rozpocet_s else None
    except ValueError:
        rozpocet = None

    # textová cache miesta pre spätnú kompatibilitu / rýchly výpis
    miesto_cache = None
    if mesto_obj:
        parts = [mesto_obj.nazov, mesto_obj.okres, mesto_obj.kraj]
        miesto_cache = ", ".join([p for p in parts if p])

    novy = Dopyt(
        typ_akcie=typ_akcie or None,
        datum=datum,
        cas_od=cas_od,
        cas_do=cas_do,
        mesto_id=mesto_id,
        miesto=miesto_cache,  # fallback text (ak by si v šablóne nepoužil FK)
        rozpocet=rozpocet,
        popis=popis or None,
        meno=meno or None,
        email=email or None,
        pouzivatel_id=(current_user.id if current_user.is_authenticated else None),
    )

    db.session.add(novy)
    db.session.commit()
    flash('Dopyt bol pridaný!', "success")

    if current_user.is_authenticated:
        return redirect(url_for('dopyty.zobraz_dopyty'))
    else:
        return redirect(url_for('main.index'))

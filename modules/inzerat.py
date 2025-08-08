# modules/inzerat.py

import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required
from models import db, Inzerat, FotoInzerat, Mesto
from PIL import Image

# --- Kategórie pre inzerát ---
KATEGORIE = [
    "Klávesy",
    "Gitary",
    "Bicie",
    "Dychové nástroje",
    "Sláčikové nástroje",
    "Ozvučenie",
    "Noty a knihy",
    "Doplnky",
    "Ostatné"
]

# Blueprint
inzerat = Blueprint('inzerat', __name__)

# Konštanta na priečinok pre fotky
UPLOAD_FOLDER = os.path.join('static', 'galeria_inzerat')

# 💾 Pridanie a zobrazenie inzerátu
@inzerat.route('/moj-bazar', methods=['GET', 'POST'])
@login_required
def moj_bazar():
    if request.method == 'POST': 
        novy_inzerat = Inzerat(
            typ=request.form.get('typ'),
            kategoria=request.form.get('kategoria'),
            mesto_id=request.form.get('mesto_id'), 
            doprava=request.form.get('doprava'),
            cena=float(request.form.get('cena', 0)),
            popis=request.form.get('popis'),
            pouzivatel_id=current_user.id
        )
        db.session.add(novy_inzerat) 
        db.session.commit()

        # 📷 Spracovanie fotiek
        fotky = request.files.getlist('fotky')
        ulozene = 0
        for fotka in fotky:
            if ulozene >= 5:
                break
            if fotka and fotka.filename != '':
                ext = os.path.splitext(fotka.filename)[1].lower()
                filename = f"{uuid.uuid4().hex}{ext}"
                cesta = os.path.join(UPLOAD_FOLDER, filename)

                try:
                    obrazok = Image.open(fotka)
                    obrazok.thumbnail((800, 800))
                    obrazok.save(cesta)

                    nova_fotka = FotoInzerat(nazov_suboru=filename, inzerat_id=novy_inzerat.id)
                    db.session.add(nova_fotka)
                    ulozene += 1
                except Exception as e:
                    print("Chyba pri ukladaní fotky:", e)
                    continue

        db.session.commit()
        flash("✅ Inzerát bol úspešne pridaný aj s fotkami!", "success")
        return redirect(url_for('inzerat.moj_bazar'))

    # GET časť
    moje_inzeraty = Inzerat.query.filter_by(pouzivatel_id=current_user.id).order_by(Inzerat.datum.desc()).all()
    mesta = Mesto.query.order_by(Mesto.nazov).all()
    return render_template('moj_bazar.html', inzeraty=moje_inzeraty, mesta=mesta, kategorie=KATEGORIE)


@inzerat.route('/zmaz-inzerat/<int:inzerat_id>')
@login_required
def zmaz_inzerat(inzerat_id):
    inzerat = Inzerat.query.get_or_404(inzerat_id)
    if inzerat.pouzivatel_id != current_user.id:
        flash("Nemáš oprávnenie zmazať tento inzerát.", "danger")
        return redirect(url_for('inzerat.moj_bazar'))

    # Zmaž všetky fotky zo súborového systému
    for fotka in inzerat.fotky:
        cesta_suboru = os.path.join(UPLOAD_FOLDER, fotka.nazov_suboru)
        if os.path.exists(cesta_suboru):
            os.remove(cesta_suboru)

    # Zmaž inzerát (aj fotky z DB cez cascade)
    db.session.delete(inzerat)
    db.session.commit()
    flash("Inzerát a jeho fotky boli zmazané.", "success")
    return redirect(url_for('inzerat.moj_bazar'))


@inzerat.route('/uprav-inzerat/<int:inzerat_id>', methods=['GET', 'POST'])
@login_required
def uprav_inzerat(inzerat_id):
    inzerat = Inzerat.query.get_or_404(inzerat_id)
    if inzerat.pouzivatel_id != current_user.id:
        flash("Nemáš oprávnenie upraviť tento inzerát.", "danger")
        return redirect(url_for('inzerat.moj_bazar'))

    if request.method == 'POST':
        # 🔁 Uloženie textových údajov
        inzerat.typ = request.form.get('typ')
        inzerat.kategoria = request.form.get('kategoria')
        inzerat.mesto_id = request.form.get('mesto_id')
        inzerat.doprava = request.form.get('doprava')
        inzerat.cena = float(request.form.get('cena', 0))
        inzerat.popis = request.form.get('popis')

        # 📸 Pridanie nových fotiek
        fotky = request.files.getlist('fotky')
        ulozene = len(inzerat.fotky)

        for fotka in fotky:
            if ulozene >= 5:
                break
            if fotka and fotka.filename != '':
                ext = os.path.splitext(fotka.filename)[1].lower()
                filename = f"{uuid.uuid4().hex}{ext}"
                cesta = os.path.join(UPLOAD_FOLDER, filename)

                try:
                    obrazok = Image.open(fotka)
                    obrazok.thumbnail((800, 800))
                    obrazok.save(cesta)

                    nova_fotka = FotoInzerat(nazov_suboru=filename, inzerat_id=inzerat.id)
                    db.session.add(nova_fotka)
                    ulozene += 1
                except Exception as e:
                    print("Chyba pri ukladaní fotky:", e)
                    continue

        db.session.commit()
        flash("✅ Inzerát bol úspešne upravený!", "success")
        return redirect(url_for('inzerat.moj_bazar'))

    # Zobrazenie edit formu
    mesta = Mesto.query.order_by(Mesto.nazov).all()
    return render_template('uprav_inzerat.html', inzerat=inzerat, mesta=mesta, kategorie=KATEGORIE)
@inzerat.route('/zmaz-fotku/<int:foto_id>')
@login_required
def zmaz_fotku(foto_id):
    fotka = FotoInzerat.query.get_or_404(foto_id)
    inzerat = Inzerat.query.get_or_404(fotka.inzerat_id)

    if inzerat.pouzivatel_id != current_user.id:
        flash("Nemáš oprávnenie zmazať túto fotku.", "danger")
        return redirect(url_for('inzerat.moj_bazar'))

    # Zmaž súbor zo súborového systému
    cesta = os.path.join(UPLOAD_FOLDER, fotka.nazov_suboru)
    if os.path.exists(cesta):
        os.remove(cesta)

    # Zmaž z databázy
    db.session.delete(fotka)
    db.session.commit()

    flash("🗑️ Fotka bola odstránená.", "success")
    return redirect(url_for('inzerat.uprav_inzerat', inzerat_id=inzerat.id))

@inzerat.route('/bazar')
def bazar_verejny():
    # vstupy z query stringu
    page = request.args.get('page', 1, type=int)
    typ = (request.args.get('typ') or '').strip() or None
    kategoria = (request.args.get('kategoria') or '').strip() or None
    mesto_id = request.args.get('mesto', type=int)

    q = Inzerat.query

    if typ:
        q = q.filter(Inzerat.typ == typ)
    if kategoria:
        q = q.filter(Inzerat.kategoria == kategoria)
    if mesto_id:
        q = q.filter(Inzerat.mesto_id == mesto_id)

    q = q.order_by(Inzerat.datum.desc())

    # error_out=False -> nevyhodí 404 pri zlej page, dá prázdny výsledok
    pagination = q.paginate(page=page, per_page=12, error_out=False)
    inzeraty = pagination.items

    # dáta pre filtre
    typy = [t[0] for t in db.session.query(Inzerat.typ).distinct().all()]
    kategorie = [k[0] for k in db.session.query(Inzerat.kategoria).distinct().all()]
    mesta = Mesto.query.order_by(Mesto.nazov.asc()).all()

    return render_template(
        'bazar.html',
        inzeraty=inzeraty,
        pagination=pagination,
        typy=typy,
        kategorie=kategorie,
        mesta=mesta,
        vybrany_typ=typ,
        vybrana_kategoria=kategoria,
        vybrane_mesto=mesto_id
    )

@inzerat.route('/bazar/<int:inzerat_id>')
def detail(inzerat_id):
    inz = Inzerat.query.get_or_404(inzerat_id)
    return render_template('detail_inzeratu.html', inzerat=inz)

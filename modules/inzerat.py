# modules/inzerat.py

import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required
from models import db, Inzerat, FotoInzerat, Mesto
from PIL import Image

# Blueprint
inzerat = Blueprint('inzerat', __name__)

# Konštanta na priečinok pre fotky
UPLOAD_FOLDER = os.path.join('static', 'galeria_inzerat')

# 💾 Pridanie inzerátu s možnosťou uploadu fotiek
@inzerat.route('/pridaj-inzerat', methods=['GET', 'POST'])
@login_required
def pridaj_inzerat():
    if request.method == 'POST': 
        print("➡️ Prijaty POST request")
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
        print("🧾 Inzerát pripravený na uloženie:", novy_inzerat)
        db.session.commit()
        print("💾 Inzerát uložený do DB s ID:", novy_inzerat.id)

        # 📷 Spracovanie fotiek
        fotky = request.files.getlist('fotky')
        ulozene = 0
        print("➡️ Počet nahraných fotiek:", len(fotky))
        for fotka in fotky:
            if ulozene >= 5:
                print("➡️ Spracúvam fotku:", fotka.filename)
                break
            if fotka and fotka.filename != '':
                ext = os.path.splitext(fotka.filename)[1].lower()
                filename = f"{uuid.uuid4().hex}{ext}"
                cesta = os.path.join(UPLOAD_FOLDER, filename)

                try:
                    obrazok = Image.open(fotka)
                    obrazok.thumbnail((800, 800))
                    obrazok.save(cesta)
                    print("📷 Fotka uložená ako:", filename)

                    nova_fotka = FotoInzerat(nazov_suboru=filename, inzerat_id=novy_inzerat.id)
                    db.session.add(nova_fotka)
                    ulozene += 1
                except Exception as e:
                    print("Chyba pri ukladaní fotky:", e)
                    continue

        db.session.commit()
        flash("✅ Inzerát bol úspešne pridaný aj s fotkami!", "success")
        return redirect(url_for('inzerat.moj_bazar'))
    
    mesta = Mesto.query.order_by(Mesto.nazov).all()
    inzeraty = Inzerat.query.filter_by(pouzivatel_id=current_user.id).order_by(Inzerat.datum.desc()).all()
    return render_template('pridaj_inzerat.html', mesta=mesta, inzeraty=inzeraty)

# 🛒 Výpis mojich inzerátov
@inzerat.route('/moj-bazar')
@login_required
def moj_bazar():
    moje_inzeraty = Inzerat.query.filter_by(pouzivatel_id=current_user.id).order_by(Inzerat.datum.desc()).all()
    mesta = Mesto.query.order_by(Mesto.nazov).all()
    return render_template('moj_bazar.html', inzeraty=moje_inzeraty, mesta=mesta)


# ❌ Mazanie inzerátu
@inzerat.route('/zmaz-inzerat/<int:inzerat_id>')
@login_required
def zmaz_inzerat(inzerat_id):
    inzerat = Inzerat.query.get_or_404(inzerat_id)
    if inzerat.pouzivatel_id != current_user.id:
        flash("Nemáš oprávnenie zmazať tento inzerát.", "danger")
        return redirect(url_for('inzerat.moj_bazar'))  
    
    db.session.delete(inzerat)
    db.session.commit()
    flash("Inzerát bol zmazaný.", "success")
    return redirect(url_for('inzerat.moj_bazar'))  

@inzerat.route('/uprav-inzerat/<int:inzerat_id>', methods=['GET', 'POST'])
@login_required
def uprav_inzerat(inzerat_id):
    inzerat = Inzerat.query.get_or_404(inzerat_id)
    if inzerat.pouzivatel_id != current_user.id:
        flash("Nemáš oprávnenie upravovať tento inzerát.", "danger")
        return redirect(url_for('inzerat.moj_bazar'))
    
    if request.method == 'POST':
        inzerat.typ = request.form.get('typ')
        inzerat.kategoria = request.form.get('kategoria')
        inzerat.mesto_id = request.form.get('mesto_id')
        inzerat.doprava = request.form.get('doprava')
        inzerat.cena = float(request.form.get('cena', 0))
        inzerat.popis = request.form.get('popis')
        db.session.commit()
        flash("✅ Inzerát bol upravený.", "success")
        return redirect(url_for('inzerat.moj_bazar'))

    mesta = Mesto.query.order_by(Mesto.nazov).all()
    return render_template('uprav_inzerat.html', inzerat=inzerat, mesta=mesta)


import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from models import Pouzivatel, db, GaleriaPouzivatel, VideoPouzivatel

uzivatel = Blueprint('uzivatel', __name__)
profil_blueprint = Blueprint('profil', __name__)

# 🔹 Test endpoint
@uzivatel.route('/test')
def test():
    return "Blueprint uzivatel funguje!"

# 🔹 Domovská stránka
@uzivatel.route('/')
def index():
    return render_template('index.html')

# 🔹 Login
@uzivatel.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        heslo = request.form['heslo']
        pouzivatel = Pouzivatel.query.filter_by(email=email).first()

        if pouzivatel and pouzivatel.over_heslo(heslo):
            login_user(pouzivatel)
            flash("Prihlásenie prebehlo úspešne.", "success")
            return redirect(url_for('uzivatel.profil'))
        else:
            flash("Nesprávne prihlasovacie údaje.", "warning")
            return redirect(url_for('uzivatel.login'))

    return render_template('login.html')

# 🔹 Registrácia
@uzivatel.route('/registracia', methods=['GET', 'POST'])
def registracia():
    if request.method == 'POST':
        prezyvka = request.form['prezyvka']
        meno = request.form['meno']
        priezvisko = request.form['priezvisko']
        email = request.form['email']
        heslo = generate_password_hash(request.form['heslo'])  # 🔐 hashovanie
        instrument = request.form['instrument']
        doplnkovy_nastroj = request.form['doplnkovy_nastroj']
        obec = request.form['obec']

        existujuci = Pouzivatel.query.filter(
            (Pouzivatel.email == email) | (Pouzivatel.prezyvka == prezyvka)
        ).first()

        if existujuci:
            flash("Používateľ s týmto e-mailom alebo prezývkou už existuje.", "warning")
            return redirect(url_for('uzivatel.registracia'))

        novy = Pouzivatel(
            prezyvka=prezyvka,
            meno=meno,
            priezvisko=priezvisko,
            email=email,
            heslo=heslo,
            instrument=instrument,
            doplnkovy_nastroj=doplnkovy_nastroj,
            obec=obec
        )

        db.session.add(novy)
        db.session.commit()
        flash('Registrácia prebehla úspešne.', "success")
        return redirect(url_for('uzivatel.login'))

    return render_template('modals/registracia.html')

# 🔹 Logout
@uzivatel.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('uzivatel.index'))

# 🔹 Profil – úprava údajov
@uzivatel.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    pouzivatel = current_user

    if request.method == 'POST':
        pouzivatel.prezyvka = request.form.get('prezyvka')
        pouzivatel.meno = request.form.get('meno')
        pouzivatel.priezvisko = request.form.get('priezvisko')
        pouzivatel.email = request.form.get('email')
        pouzivatel.obec = request.form.get('obec')
        pouzivatel.instrument = request.form.get('instrument')
        pouzivatel.doplnkovy_nastroj = request.form.get('doplnkovy_nastroj')
        pouzivatel.bio = request.form.get('bio')
        db.session.commit()
        flash("Profil bol úspešne upravený", "success")
        return redirect(url_for('uzivatel.profil'))

    skupina = pouzivatel.skupina_clen[0] if pouzivatel.skupina_clen else None
    galeria = skupina.galeria if skupina else []
    youtube_videa = pouzivatel.videa  # ✅ OPRAVENÉ

    return render_template('modals/profil.html',
                           pouzivatel=pouzivatel,
                           skupina=skupina,
                           galeria=galeria,
                           youtube_videa=youtube_videa)


# 🔹 Upload profilovej fotky
@uzivatel.route('/upload_fotka', methods=['POST'])
@login_required
def upload_fotka():
    if 'profil_fotka' not in request.files:
        flash("Nebol vybraný žiadny súbor.", "danger")
        return redirect(url_for('uzivatel.profil'))


    file = request.files['profil_fotka']
    if file.filename == '':
        flash("Nebol vybraný žiadny súbor.", "danger")
        return redirect(url_for('uzivatel.profil'))

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.root_path, 'static', 'profilovky', filename)
        file.save(filepath)

        pouzivatel = current_user
        pouzivatel.profil_fotka = filename
        db.session.commit()

        flash("Profilová fotka bola úspešne nahraná.", "success")
    return redirect(url_for('uzivatel.profil'))

# 🔹 Odstránenie profilovej fotky
@uzivatel.route('/odstranit_fotku')
@login_required
def odstranit_fotku():
    pouzivatel = current_user

    if pouzivatel.profil_fotka:
        filepath = os.path.join(current_app.root_path, 'static', 'profilovky', pouzivatel.profil_fotka)
        if os.path.exists(filepath):
            os.remove(filepath)
        pouzivatel.profil_fotka = None
        db.session.commit()

    flash("Profilová fotka bola odstránená.", "success")
    return redirect(url_for('uzivatel.profil'))

# 🔹 Upload fotky do galérie používateľa
@profil_blueprint.route('/profil/galeria', methods=['POST'])
@login_required
def nahraj_fotku():
    subor = request.files.get('foto')
    if subor and subor.filename != '':
        filename = secure_filename(subor.filename)
        cesta = os.path.join('static/galeria_pouzivatel', filename)
        subor.save(cesta)

        nova = GaleriaPouzivatel(nazov_suboru=filename, pouzivatel_id=current_user.id)
        db.session.add(nova)
        db.session.commit()

    return redirect(url_for('uzivatel.profil'))

# 🔹 Odstránenie fotky z galérie používateľa
@profil_blueprint.route('/profil/galeria/zmaz/<int:id>', methods=['POST'])
@login_required
def zmaz_fotku(id):
    fotka = GaleriaPouzivatel.query.get_or_404(id)
    if fotka.pouzivatel_id == current_user.id:
        cesta = os.path.join('static/galeria_pouzivatel', fotka.nazov_suboru)
        if os.path.exists(cesta):
            os.remove(cesta)
        db.session.delete(fotka)
        db.session.commit()
    return redirect(url_for('uzivatel.profil'))

@profil_blueprint.route('/pridaj_video', methods=['POST'])
@login_required
def pridaj_video():
    url = request.form['youtube_url']
    popis = request.form.get('popis')
    nove_video = VideoPouzivatel(youtube_url=url, popis=popis, pouzivatel_id=current_user.id)
    db.session.add(nove_video)
    db.session.commit()
    flash("Video bolo pridané.", "success")
    return redirect(url_for('uzivatel.profil'))


@profil_blueprint.route('/zmaz_video/<int:id>', methods=['POST'])
@login_required
def zmaz_video(id):
    video = VideoPouzivatel.query.get_or_404(id)
    if video.pouzivatel_id != current_user.id:
        abort(403)
    db.session.delete(video)
    db.session.commit()
    flash("Video bolo zmazané.", "success")
    return redirect(url_for('uzivatel.profil'))




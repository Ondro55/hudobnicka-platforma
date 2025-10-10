import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func
from datetime import datetime
from flask import url_for
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from alembic import op
import sqlalchemy as sa

db = SQLAlchemy()

import json

class Pouzivatel(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    # základ
    prezyvka = db.Column(db.String(50), unique=True, nullable=False)
    meno = db.Column(db.String(100))
    priezvisko = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    heslo = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text)
    obec = db.Column(db.String(100))
    datum_registracie = db.Column(db.DateTime, default=datetime.utcnow)
    aktivny = db.Column(db.Boolean, default=True)
    profil_fotka = db.Column(db.String(200))

    # historické pole – nepoužívame na zobrazenie, ale nechávame
    zamerania = db.Column(db.Text, nullable=True)

    # legacy polia (ak ich ešte niekde posiela registrácia)
    instrument = db.Column(db.String(100))
    doplnkovy_nastroj = db.Column(db.String(100))

    # práva / účet
    is_admin = db.Column(db.Boolean, default=False)
    is_moderator = db.Column(db.Boolean, default=False)
    strikes_count = db.Column(db.Integer, default=0, nullable=False)
    banned_until = db.Column(db.DateTime, nullable=True)
    banned_reason = db.Column(db.String(255), nullable=True)

    typ_subjektu = db.Column(db.String(10), default='fyzicka')  # 'fyzicka' | 'ico'
    ico = db.Column(db.String(20), nullable=True)
    organizacia_nazov = db.Column(db.String(150), nullable=True)
    plan = db.Column(db.String(20), nullable=False, default='free')
    account_type = db.Column(db.String(20), nullable=False, default='individual')
    searchable = db.Column(db.Boolean, nullable=False, default=False)
    is_vip = db.Column(db.Boolean, nullable=False, default=False)
    billing_exempt = db.Column(db.Boolean, nullable=False, default=False)
   
    # vzhľad / preferencie
    theme = db.Column(db.String(20), default="system", nullable=False)

    # súkromie
    verejny_ucet = db.Column(db.Boolean, default=False, nullable=False)
    zverejnovat_videa  = db.Column(db.Boolean, default=True,  nullable=False)
    povolit_hodnotenie = db.Column(db.Boolean, default=True,  nullable=False)

    # sledovanie
    follow_mode     = db.Column(db.String(16),  default="all", nullable=False)  # 'all' | 'custom'
    follow_zanre    = db.Column(db.String(255), default="",     nullable=False) # CSV
    follow_entities = db.Column(db.String(255), default="",     nullable=False) # CSV
   

    __table_args__ = (
        CheckConstraint("theme IN ('system','light','dark','blue','green','red')", name="ck_user_theme"),
        CheckConstraint("follow_mode IN ('all','custom')",           name="ck_user_follow_mode"),
        # rýchle filtre v appke
        Index("ix_user_visible", "aktivny", "is_deleted", "verejny_ucet"),
    )
    # ratings user
    rating_count = db.Column(db.Integer, default=0, nullable=False)
    rating_sum   = db.Column(db.Integer, default=0, nullable=False)
    rating_avg   = db.Column(db.Float,   default=0.0, nullable=False)
    rating_bayes = db.Column(db.Float,   default=0.0, nullable=False)

    # vymazanie účtu
    erase_requested_at = db.Column(db.DateTime)
    erase_deadline_at  = db.Column(db.DateTime)
    is_deleted         = db.Column(db.Boolean, default=False, nullable=False)
    erase_token   = db.Column(db.String(128), index=True)
    erase_feedback = db.Column(db.Text)       # uložíme JSON/text dôvodov
    erased_at     = db.Column(db.DateTime)

    @property
    def erase_pending(self) -> bool:
        # Čaká na potvrdenie, ak existuje token a nevypršal deadline
        if not self.erase_token:
            return False
        return (self.erase_deadline_at is None) or (datetime.utcnow() < self.erase_deadline_at)

        # --- FO: single-stĺpce – kvôli kompatibilite so starou registráciou ---
    rola = db.Column(db.String(40), index=True)  # primárna rola

    # HUDOBNÍK
    hud_oblast = db.Column(db.String(40), index=True)  # spev|klavesy|gitara|...
    hud_spec = db.Column(db.Text)  # CSV

    # TANEČNÍK
    tanec_spec = db.Column(db.Text)  # CSV
    tanec_ine = db.Column(db.String(120))

    # MODERÁTOR
    moderator_podrola = db.Column(db.String(40), index=True)  # historicky string/CSV

    # UČITEĽ HUDBY
    ucitel_predmety = db.Column(db.Text)  # CSV
    ucitel_ine = db.Column(db.String(120))

    # „Iné“
    rola_ina = db.Column(db.String(200))

    # === NOVÉ: multi-rola v JSON forme ===
    # Očakávaný tvar:
    # {
    #   "hudobnik": {"hud_oblast":"gitara","hud_spec":["elektricka","akusticka"]},
    #   "tanecnik": {"tanec_spec":["street"],"tanec_ine":null},
    #   "moderator": {"podrola": ["moderator","moderator_hudobnych_akcií"]},
    #   "ucitel_hudby": {"ucitel_predmety":["gitara","teoria"],"ucitel_ine":null},
    #   "simple_roles": ["fotograf","videograf","zvukar","osvetlovac","technik_podia","producent","skladatel"]
    # }
    # (Pre spätnú kompatibilitu ak by si mal kedysi kľúče 'fotograf': {} atď., tiež ich zoberieme do úvahy.)
    role_data = db.Column(db.Text)

    # --- IČO údaje ---
    org_zaradenie = db.Column(db.String(40), index=True)
    org_zaradenie_ine = db.Column(db.String(120))
    dic = db.Column(db.String(20))
    ic_dph = db.Column(db.String(20))
    sidlo_ulica = db.Column(db.String(120))
    sidlo_psc = db.Column(db.String(10), index=True)
    sidlo_mesto = db.Column(db.String(80), index=True)

    # --- vzťahy ---
    galeria = db.relationship('GaleriaPouzivatel', back_populates='pouzivatel',
                              lazy=True, cascade='all, delete-orphan')
    videa = db.relationship('VideoPouzivatel', back_populates='pouzivatel',
                            lazy=True, cascade='all, delete-orphan')

    # --- auth helpers ---
    def over_heslo(self, zadane_heslo):
        return check_password_hash(self.heslo, zadane_heslo)

    def nastav_heslo(self, heslo):
        self.heslo = generate_password_hash(heslo)

    # --- URL helpers ---
    @property
    def profil_fotka_url(self):
        if self.profil_fotka:
            return url_for('static', filename=f'profilovky/{self.profil_fotka}')
        return url_for('static', filename='profilovky/default.png')

    @property
    def profil_url(self):
        for endpoint, params in [
            ('profil.detail', {'user_id': self.id}),
            ('profil.view', {'user_id': self.id}),
            ('uzivatel.profil_detail', {'id': self.id}),
            ('uzivatel.profil_public', {'id': self.id}),
        ]:
            try:
                return url_for(endpoint, **params)
            except Exception:
                continue
        try:
            return url_for('uzivatel.profil')
        except Exception:
            return '#'

    @property
    def is_banned(self) -> bool:
        return self.banned_until is not None and datetime.utcnow() < self.banned_until

    # ====== MAPPINGY ======
    _ROLE_LABELS = {
        'hudobnik': 'Hudobník',
        'tanecnik': 'Tanečník',
        'moderator': 'Moderátor akcií',
        'fotograf': 'Fotograf',
        'videograf': 'Videograf',
        'zvukar': 'Zvukár',
        'osvetlovac': 'Osvetľovač',
        'technik_podia': 'Technik pódia / Roadie',
        'producent': 'Producent / Beatmaker',
        'skladatel': 'Skladateľ / Aranžér',
        'ucitel_hudby': 'Učiteľ hudby',
        'ine': 'Iné',
    }

    _SIMPLE_ROLE_LABELS = {
        'fotograf': 'Fotograf',
        'videograf': 'Videograf',
        'zvukar': 'Zvukár',
        'osvetlovac': 'Osvetľovač',
        'technik_podia': 'Technik pódia / Roadie',
        'producent': 'Producent / Beatmaker',
        'skladatel': 'Skladateľ / Aranžér',
    }

    _HUD_OBLAST_LABELS = {
        'spev': 'Spev',
        'klavesy': 'Klávesy',
        'gitara': 'Gitara',
        'bicie': 'Bicie / Perkusie',
        'slacikove': 'Sláčikové',
        'dychove': 'Dychové',
        'dj': 'DJ',
        'elektronika': 'Elektronika (live)',
        'folklorne': 'Folklórne',
        'ine': 'Iné',
    }

    # !!! rozšírené špecifikácie, aby sa pekne zobrazovali všetky checkboxy z UI
    _HUD_SPEC_LABELS = {
        # spev
        'solo': 'Sólo', 'vokal': 'Vokál', 'zbor': 'Zbor',
        'sprievod': 'Sprievod', 'kapela': 'Kapela',

        # klávesy
        'klavir': 'Klavír', 'keyboard': 'Keyboard', 'synth': 'Synthesizer', 'organ': 'Organ / Hammond',

        # gitara
        'elektricka': 'Elektrická', 'akusticka': 'Akustická', 'klasicka': 'Klasická', 'basgitara': 'Basgitara',

        # bicie / perkusie
        'bicie_suprava': 'Bicie súprava', 'perkusie': 'Perkusie', 'cajon': 'Cajon',

        # sláčikové
        'husle': 'Husle', 'viola': 'Viola', 'violoncello': 'Violončelo', 'kontrabas': 'Kontrabas',

        # dychové
        'saxofon': 'Saxofón', 'klarinet': 'Klarinet', 'priecna_flauta': 'Priečna flauta',
        'trumpeta': 'Trumpeta', 'pozoun': 'Pozoun', 'lesny_rog': 'Lesný roh', 'tuba': 'Tuba',

        # DJ
        'svadobny': 'Svadobný', 'oldies': 'Oldies', '80s_90s': '80s/90s', 'komercne': 'Komerčné', 'house': 'House', 'techno': 'Techno',

        # elektronika
        'sampler': 'Sampler', 'drum_machine': 'Drum machine', 'live_perf': 'Live performance',

        # folklórne
        'cimbal': 'Cimbal', 'akordeon': 'Akordeón', 'heligonka': 'Heligónka', 'gajdy': 'Gajdy', 'fujara': 'Fujara',

        # fallback
        'ine': 'Iné',
    }

    _TANEC_LABELS = {
        'moderne': 'Moderné / Contemporary',
        'folklor_subor': 'Folklórny súbor',
        'latino': 'Latino (Salsa/Bachata)',
        'street': 'Street / Hip-hop',
        'ballroom': 'Ballroom (Štandard/Latina)',
        'spolocenske': 'Spoločenské / Club',
        'pedagog': 'Tanečný pedagóg',
        'ine': 'Iné',
    }

    _MODERATOR_PODROLA_LABELS = {
        'staresi': 'Starejší',
        'moderator': 'Moderátor',
        'moderator_hudobnych_akcii': 'Moderátor hudobných akcií',
    }

    _UCITEL_LABELS = {
        'klavir': 'Klavír', 'gitara': 'Gitara', 'husle': 'Husle', 'flauta': 'Flauta',
        'saxofon': 'Saxofón', 'klarinet': 'Klarinet', 'trumpeta': 'Trúbka', 'bicie': 'Bicie',
        'spev': 'Spev', 'akordeon': 'Akordeón', 'heligonka': 'Heligónka', 'teoria': 'Hudobná teória',
        'ine': 'Iné',
    }

    # ====== JSON helpers ======
    def _get_role_data(self) -> dict:
        try:
            return json.loads(self.role_data) if self.role_data else {}
        except Exception:
            return {}

    def _set_role_data(self, data: dict):
        self.role_data = json.dumps(data, ensure_ascii=False)

    @property
    def role_data_dict(self) -> dict:
        return self._get_role_data()

    def set_role_block(self, role: str, data: dict | None):
        obj = self._get_role_data()
        if data is None:
            obj.pop(role, None)
        else:
            obj[role] = data
        self._set_role_data(obj)

    @staticmethod
    def _split_csv(v: str):
        if not v:
            return []
        return [s.strip() for s in v.split(',') if s and s.strip()]

    # Na predvyplnenie jednoduchých rolí v edite
    @property
    def simple_roles_selected(self):
        try:
            data = json.loads(self.role_data or "{}")
            return [r for r in data.get("simple_roles", []) if r]
        except Exception:
            return []

    @staticmethod
    def _list_to_csv(lst):
        if not lst:
            return ""   # dôležité – nie None
        out, seen = [], set()
        for x in lst:
            s = (x or "").strip()
            if s and s not in seen:
                seen.add(s); out.append(s)
        return ",".join(out)

    @property
    def is_active(self) -> bool:
        if self.is_deleted:
            return False
        if self.is_banned:
            return False
        return bool(self.aktivny)


    # ====== Zobrazenie „Zamerania“ – preferuj role_data; inak fallback ======
    def zamerania_list(self):
        import json

        # mapy
        RL = self._ROLE_LABELS
        HO = self._HUD_OBLAST_LABELS
        HS = self._HUD_SPEC_LABELS
        TN = self._TANEC_LABELS
        MD = self._MODERATOR_PODROLA_LABELS
        UC = self._UCITEL_LABELS
        SR = self._SIMPLE_ROLE_LABELS

        # pomocníci
        def dedup_keep_order(lst):
            out, seen = [], set()
            for x in lst:
                if not x:
                    continue
                x = x.strip()
                if x and x not in seen:
                    seen.add(x); out.append(x)
            return out

        def add_group(role_key, items, out_list):
            items = dedup_keep_order(items)
            if not items:
                return
            label = RL.get(role_key, role_key)
            out_list.append(f"{label} – {', '.join(items)}")

        # načítaj JSON
        try:
            data = json.loads(self.role_data or "{}")
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}

        out = []

        # ===== HUDOBNÍK (leaf = špecifikácie; ak nie sú, aspoň oblasť) =====
        hud_items = []
        det = data.get('hudobnik') or {}
        if isinstance(det, dict):
            ho = (det.get('hud_oblast') or '').strip()
            specs = det.get('hud_spec') or []
            if specs:
                for sp in specs:
                    hud_items.append(HS.get(sp, sp))
            elif ho:
                hud_items.append(HO.get(ho, ho))
        # legacy doplnenie
        legacy_ho = (self.hud_oblast or '').strip()
        legacy_specs = [s.strip() for s in (self.hud_spec or '').split(',') if s.strip()]
        if legacy_specs:
            for sp in legacy_specs:
                hud_items.append(HS.get(sp, sp))
        elif legacy_ho:
            hud_items.append(HO.get(legacy_ho, legacy_ho))
        add_group('hudobnik', hud_items, out)

        # ===== TANEČNÍK =====
        tan_items = []
        det = data.get('tanecnik') or {}
        if isinstance(det, dict):
            for sp in (det.get('tanec_spec') or []):
                tan_items.append(TN.get(sp, sp))
            ti = (det.get('tanec_ine') or '').strip()
            if ti: tan_items.append(ti)
        # legacy
        for sp in [s.strip() for s in (self.tanec_spec or '').split(',') if s.strip()]:
            tan_items.append(TN.get(sp, sp))
        if (self.tanec_ine or '').strip():
            tan_items.append(self.tanec_ine.strip())
        add_group('tanecnik', tan_items, out)

        # ===== MODERÁTOR =====
        mod_items = []
        det = data.get('moderator') or {}
        if isinstance(det, dict):
            pod = det.get('podrola') or []
            if isinstance(pod, str):
                pod = [s.strip() for s in pod.split(',') if s.strip()]
            for sp in pod:
                mod_items.append(MD.get(sp, sp))
        # legacy
        for sp in [s.strip() for s in (self.moderator_podrola or '').split(',') if s.strip()]:
            mod_items.append(MD.get(sp, sp))
        add_group('moderator', mod_items, out)

        # ===== UČITEĽ HUDBY =====
        uc_items = []
        det = data.get('ucitel_hudby') or {}
        if isinstance(det, dict):
            for sp in (det.get('ucitel_predmety') or []):
                uc_items.append(UC.get(sp, sp))
            ui = (det.get('ucitel_ine') or '').strip()
            if ui: uc_items.append(ui)
        # legacy
        for sp in [s.strip() for s in (self.ucitel_predmety or '').split(',') if s.strip()]:
            uc_items.append(UC.get(sp, sp))
        if (self.ucitel_ine or '').strip():
            uc_items.append(self.ucitel_ine.strip())
        add_group('ucitel_hudby', uc_items, out)

        # ===== INÉ =====
        ine_items = []
        det = data.get('ine') or {}
        if isinstance(det, dict):
            ri = (det.get('rola_ina') or '').strip()
            if ri: ine_items.append(ri)
        if (self.rola == 'ine') and (self.rola_ina or '').strip():
            ine_items.append(self.rola_ina.strip())
        # ak niečo je, zobrazíme "Iné – text"
        add_group('ine', ine_items, out)

        # ===== SIMPLE ROLES (Fotograf, Videograf, …) – idú samostatne =====
        simple = []
        # nové JSON pole
        simple.extend(data.get('simple_roles', []) or [])
        # spätná kompatibilita: ak by boli priamo kľúče 'fotograf': {}
        for key in SR.keys():
            if key in data:
                simple.append(key)
        simple = dedup_keep_order(simple)
        for sr in simple:
            out.append(SR.get(sr, sr))

        # prázdny zoznam -> nech šablóna ukáže „—“
        return out




class Inzerat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    typ = db.Column(db.String(50))
    kategoria = db.Column(db.String(50))
    mesto = db.Column(db.String(100))
    doprava = db.Column(db.String(50))
    cena = db.Column(db.Float)
    popis = db.Column(db.Text)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

    mesto_id = db.Column(db.Integer, db.ForeignKey('mesto.id', name='fk_inzerat_mesto'), nullable=True)
    mesto_objekt = db.relationship('Mesto', backref='inzeraty')

    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    pouzivatel = db.relationship('Pouzivatel', backref='inzeraty')

    fotky = db.relationship('FotoInzerat', backref='inzerat', cascade='all, delete-orphan')


class FotoInzerat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov_suboru = db.Column(db.String(200), nullable=False)
    inzerat_id = db.Column(db.Integer, db.ForeignKey('inzerat.id'), nullable=False)


# 🧩 Pomocná tabuľka pre Many-to-Many medzi skupina a Pouzivatel
skupina_clenovia = db.Table('skupina_clenovia',
    db.Column('skupina_id', db.Integer, db.ForeignKey('skupina.id')),
    db.Column('pouzivatel_id', db.Integer, db.ForeignKey('pouzivatel.id'))
)

class Dopyt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meno = db.Column(db.String(100))
    email = db.Column(db.String(120))
    typ_akcie = db.Column(db.String(100))
    miesto = db.Column(db.String(100))  # voľný text
    datum = db.Column(db.Date)
    cas_od = db.Column(db.Time)
    cas_do = db.Column(db.Time)
    popis = db.Column(db.Text)
    rozpocet = db.Column(db.Float)

    # FK na tabuľku miest
    mesto_id = db.Column(db.Integer, db.ForeignKey('mesto.id'), nullable=True)
    mesto_ref = db.relationship('Mesto')  # PREMENOVANÉ z `mesto` -> `mesto_ref`

    aktivny = db.Column(db.Boolean, default=True)
    zmazany_at = db.Column(db.DateTime, nullable=True)

    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)
    pouzivatel = db.relationship('Pouzivatel', backref='dopyty')

    # časové stopy
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # kedy (ak vôbec) sme poslali CTA mail zadávateľovi
    cta_sent_at = db.Column(db.DateTime, nullable=True)


class Skupina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(100), nullable=False)
    zaner = db.Column(db.String(100))
    mesto = db.Column(db.String(100))
    email = db.Column(db.String(120))
    web = db.Column(db.String(255))
    popis = db.Column(db.Text)
    profil_fotka_skupina = db.Column(db.String(120), nullable=True)
    datum_vytvorenia = db.Column(db.DateTime, default=datetime.utcnow)

    zakladatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    zakladatel = db.relationship('Pouzivatel', backref='kapely_zalozene')

    clenovia = db.relationship('Pouzivatel', secondary=skupina_clenovia, backref='skupina_clen')

    galeria = db.relationship('GaleriaSkupina', back_populates='skupina', cascade='all, delete-orphan')
    videa = db.relationship('VideoSkupina', back_populates='skupina', cascade='all, delete-orphan')


class GaleriaPouzivatel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov_suboru = db.Column(db.String(200), nullable=False)
    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)

    pouzivatel = db.relationship('Pouzivatel', back_populates='galeria')


class VideoPouzivatel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(255), nullable=False)
    popis = db.Column(db.String(255))
    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)

    pouzivatel = db.relationship('Pouzivatel', back_populates='videa')


class GaleriaSkupina(db.Model):
    __tablename__ = 'galeria_skupina'

    id = db.Column(db.Integer, primary_key=True)
    nazov_suboru = db.Column(db.String(200), nullable=False)
    skupina_id = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=False)

    skupina = db.relationship('Skupina', back_populates='galeria')


class VideoSkupina(db.Model):
    __tablename__ = 'video_skupina'

    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(300), nullable=False)
    popis = db.Column(db.String(200))
    skupina_id = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=False)

    skupina = db.relationship('Skupina', back_populates='videa')

# Kalendar#
class Udalost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(100), nullable=False)
    popis = db.Column(db.Text)
    datum = db.Column(db.Date, nullable=False)
    cas_od = db.Column(db.Time, nullable=True)
    cas_do = db.Column(db.Time, nullable=True)
    miesto = db.Column(db.String(150), nullable=True)
    poznamka = db.Column(db.Text, nullable=True)
    celodenne = db.Column(db.Boolean, default=False)

    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)
    pouzivatel = db.relationship('Pouzivatel', backref='udalosti')

    skupina_id = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=True)
    skupina = db.relationship('Skupina', backref='udalosti')

class Mesto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(100), nullable=False)
    okres = db.Column(db.String(100), nullable=True)
    kraj = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"{self.nazov} ({self.okres}, {self.kraj})"

class Sprava(db.Model):
    __tablename__ = "spravy"
    id = db.Column(db.Integer, primary_key=True)
    obsah = db.Column(db.Text, nullable=False)
    datum = db.Column(db.DateTime, default=datetime.utcnow)

    od_id   = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    komu_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)  # <- zmenené na True
    komu_email = db.Column(db.String(255), nullable=True)  # <- NOVÉ

    deleted_by_sender    = db.Column(db.Boolean, default=False)
    deleted_by_recipient = db.Column(db.Boolean, default=False)

    inzerat_id = db.Column(db.Integer, db.ForeignKey('inzerat.id'), nullable=True)
    dopyt_id   = db.Column(db.Integer, db.ForeignKey('dopyt.id'),   nullable=True)

    precitane = db.Column(db.Boolean, default=False)
    
    od   = db.relationship('Pouzivatel', foreign_keys=[od_id])
    komu = db.relationship('Pouzivatel', foreign_keys=[komu_id])
    inzerat = db.relationship('Inzerat', backref='spravy')

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=True)
    reporter = db.relationship('Pouzivatel', foreign_keys=[reporter_id])

    entity_type = db.Column(db.String(30), nullable=False)  # 'sprava' | 'inzerat' | 'dopyt' | 'profil'
    entity_id   = db.Column(db.Integer, nullable=False)

    reason = db.Column(db.String(50), nullable=False)  # 'obtažovanie','spam','nevhodny_obsah','fake','ine'
    details = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default='open', nullable=False)  # 'open' | 'resolved' | 'ignored'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'))
    resolved_by = db.relationship('Pouzivatel', foreign_keys=[resolved_by_id])
    resolution_note = db.Column(db.Text, nullable=True)

class ModerationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    actor = db.relationship('Pouzivatel')
    action = db.Column(db.String(50), nullable=False)   # 'hide','warn','tempban','permban','delete','restore'
    target_type = db.Column(db.String(30), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class SkupinaPozvanka(db.Model):
    __tablename__ = 'skupina_pozvanka'

    id          = db.Column(db.Integer, primary_key=True)
    token       = db.Column(db.String(64), unique=True, nullable=False)
    stav        = db.Column(db.String(12), default='pending', nullable=False)  # pending/accepted/revoked/expired
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at  = db.Column(db.DateTime)

    skupina_id  = db.Column(db.Integer, db.ForeignKey('skupina.id'), nullable=False)
    pozvany_id  = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)
    pozval_id   = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False)

    skupina     = db.relationship('Skupina', backref='pozvanky')
    pozvany     = db.relationship('Pouzivatel', foreign_keys=[pozvany_id])
    pozval      = db.relationship('Pouzivatel', foreign_keys=[pozval_id])

    def is_valid(self) -> bool:
        if self.stav != 'pending':
            return False
        if self.expires_at and datetime.utcnow() >= self.expires_at:
            return False
        return True

# --- MODELY FÓRA ---

# Ak máš inde definované:
# from yourapp.models import Pouzivatel   # <- uprav podľa tvojej appky

class ForumCategory(db.Model):
    __tablename__ = "forum_category"
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=True, unique=True)

    topics = db.relationship("ForumTopic", back_populates="kategoria", cascade="all, delete")

class ForumTopic(db.Model):
    __tablename__ = "forum_topic"
    id = db.Column(db.Integer, primary_key=True)
    nazov = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    vytvorene_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    aktivita_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # vzťahy
    autor_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=True)  # premenuj FK ak treba
    kategoria_id = db.Column(db.Integer, db.ForeignKey("forum_category.id"), nullable=True)

    autor = db.relationship("Pouzivatel")  # premenuj podľa seba
    kategoria = db.relationship("ForumCategory", back_populates="topics")
    posts = db.relationship("ForumPost", back_populates="topic", cascade="all, delete-orphan")

    @property
    def pocet_odpovedi(self) -> int:
        # jednoduché – na štart stačí; neskôr vieme nahradiť agregáciou
        return len(self.posts) if self.posts is not None else 0

class ForumPost(db.Model):
    __tablename__ = "forum_post"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    vytvorene_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_answer = db.Column(db.Boolean, default=False, nullable=False)

    autor_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=True)  # premenuj FK ak treba
    topic_id = db.Column(db.Integer, db.ForeignKey("forum_topic.id"), nullable=False, index=True)

    autor = db.relationship("Pouzivatel")  # premenuj podľa seba
    topic = db.relationship("ForumTopic", back_populates="posts")

class TopicWatch(db.Model):
    __tablename__ = "forum_topic_watch"
    # kto sleduje akú tému
    user_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), primary_key=True)   # premenuj podľa seba
    topic_id = db.Column(db.Integer, db.ForeignKey("forum_topic.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class RychlyDopyt(db.Model):
    __tablename__ = "rychly_dopyt"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    mesto_id = db.Column(db.Integer, db.ForeignKey("mesto.id"), nullable=True, index=True)
    mesto_ref = db.relationship("Mesto")

    autor_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=True, index=True)
    autor = db.relationship("Pouzivatel")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    plati_do = db.Column(db.DateTime, nullable=False, index=True)

    aktivny = db.Column(db.Boolean, default=True, nullable=False, index=True)
    archived_at = db.Column(db.DateTime, nullable=True)

    def is_active(self) -> bool:
        return self.aktivny and (self.plati_do is None or datetime.utcnow() < self.plati_do)
    

class ForumNotification(db.Model):
    __tablename__ = 'forum_notification'
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), index=True, nullable=False)
    topic_id  = db.Column(db.Integer, index=True, nullable=False)
    post_id   = db.Column(db.Integer, index=True, nullable=False)
    reason    = db.Column(db.String(32))         # 'reply', 'watch', 'mention'
    created_at= db.Column(db.DateTime, default=datetime.utcnow)
    read_at   = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='uq_forumnotif_user_post'),  # žiadne duplikáty
    )

    def __repr__(self):
            return f"<ForumNotification user={self.user_id} post={self.post_id} reason={self.reason}>"
    

class Podujatie(db.Model):
    __tablename__ = 'podujatie'

    id = db.Column(db.Integer, primary_key=True)
    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False, index=True)

    nazov = db.Column(db.String(120), nullable=False)
    organizator = db.Column(db.String(120), nullable=True)

    # POZOR: u teba 'miesto' slúži často ako mesto (kým nepridáme mesto_id)
    miesto = db.Column(db.String(120), nullable=True)

    # dátum + čas začiatku
    start_dt = db.Column(db.DateTime, nullable=False)

    popis = db.Column(db.Text, nullable=True)

    # 1 bulletin fotka
    foto_nazov = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Moderovanie + expirácia
    # values: 'pending' | 'publikovane' | 'zamietnute'
    stav = db.Column(db.String(20), nullable=False, default='pending', index=True)
    delete_at = db.Column(db.DateTime, nullable=True, index=True)

    autor = db.relationship('Pouzivatel', backref=db.backref('podujatia', lazy='dynamic'))

    @property
    def foto_url(self):
        from flask import url_for
        if self.foto_nazov:
            return url_for('static', filename=f'podujatia/{self.foto_nazov}')
        return url_for('static', filename='podujatia/event-default.svg')

    @property
    def visible_until(self):
        # fallback, ak delete_at nie je nastavené
        return (self.start_dt or datetime.utcnow()) + timedelta(days=1)

    @property
    def is_public_active(self):
        return datetime.utcnow() < self.visible_until

    @property
    def je_verejne(self) -> bool:
        """Je zaraditeľné do verejného výpisu práve teraz?"""
        if self.stav != 'publikovane':
            return False
        lim = self.delete_at or self.visible_until
        return datetime.utcnow() < lim


class Reklama(db.Model):
    __tablename__ = 'reklama'

    id = db.Column(db.Integer, primary_key=True)
    pouzivatel_id = db.Column(db.Integer, db.ForeignKey('pouzivatel.id'), nullable=False, index=True)

    nazov = db.Column(db.String(120), nullable=False)
    text = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(255), nullable=True)

    foto_nazov = db.Column(db.String(255), nullable=True)

    start_dt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_dt = db.Column(db.DateTime, nullable=True)           # ak None → berme 7 dní od startu (nižšie v property)

    is_top = db.Column(db.Boolean, nullable=False, default=False)  # topovanie
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    autor = db.relationship('Pouzivatel', backref=db.backref('reklamy', lazy='dynamic'))
    reports = db.relationship('ReklamaReport', backref='reklama', cascade='all, delete-orphan', lazy='dynamic')

    @property
    def foto_url(self):
        from flask import url_for
        if self.foto_nazov:
            return url_for('static', filename=f'reklamy/{self.foto_nazov}')
        return url_for('static', filename='podujatia/event-default.svg')  # použijeme jemnú defaultku

    def is_active_now(self):
        now = datetime.utcnow()
        if self.end_dt:
            return self.start_dt <= now <= self.end_dt
        # defaultne 7 dní, ak end_dt nie je zadané
        from datetime import timedelta
        return self.start_dt <= now <= (self.start_dt + timedelta(days=7))


class ReklamaReport(db.Model):
    __tablename__ = "reklama_report"
    id = db.Column(db.Integer, primary_key=True)
    reklama_id = db.Column(db.Integer, db.ForeignKey("reklama.id", ondelete="CASCADE"), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey("pouzivatel.id", ondelete="SET NULL"))
    reason = db.Column(db.String(32), nullable=False)        # 'nsfw' | 'vulgar' | 'violence' | 'hate' | 'spam' | 'scam' | 'other'
    details = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    handled = db.Column(db.Boolean, default=False, nullable=False)
    handled_by = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"))
    handled_at = db.Column(db.DateTime)
    action = db.Column(db.String(16))  # 'keep' | 'pause' | 'remove' | 'warn'
    
    reporter = db.relationship('Pouzivatel', foreign_keys=[reporter_id])
    handler  = db.relationship('Pouzivatel', foreign_keys=[handled_by])


class UserRating(db.Model):
    __tablename__ = "user_rating"

    id         = db.Column(db.Integer, primary_key=True)
    ratee_id   = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=False, index=True)  # koho hodnotím
    rater_id   = db.Column(db.Integer, db.ForeignKey("pouzivatel.id"), nullable=False, index=True)  # kto hodnotí

    # palec hore/dole (doplnkové odporúčanie)
    recommend  = db.Column(db.Boolean, nullable=False, default=False)

    # 1–5 hviezdičiek, voliteľné (môže byť None, ak dá len recommend)
    stars      = db.Column(db.Integer)
    note = db.Column(db.String(500))
    # (voliteľné) kategória/skill – napr. 'klavir', 'spev' atď.
    category_key = db.Column(db.String(40))

    status     = db.Column(db.String(12), nullable=False, default="active")  # active/removed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('ratee_id', 'rater_id', name='uq_rating_pair'),
        db.Index('ix_user_rating_ratee_id', 'ratee_id'),
        db.Index('ix_user_rating_rater_id', 'rater_id'),
    )

    def is_active(self) -> bool:
        return self.status == "active"



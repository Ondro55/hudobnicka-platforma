# modules/forum.py
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from werkzeug.routing import BuildError
from models import db, ForumTopic, ForumPost, TopicWatch, Pouzivatel
import re

# POZN.: v app.py je blueprint registrovaný s url_prefix="/komunita/forum"
forum_bp = Blueprint('forum', __name__)

# =========================
# Pomocné funkcie
# =========================

def _toggle_watch(user_id: int, topic_id: int) -> bool:
    rel = TopicWatch.query.filter_by(user_id=user_id, topic_id=topic_id).first()
    if rel:
        db.session.delete(rel)
        return False
    else:
        db.session.add(TopicWatch(user_id=user_id, topic_id=topic_id))
        return True

def _ensure_watch(user_id: int, topic_id: int) -> None:
    if not TopicWatch.query.filter_by(user_id=user_id, topic_id=topic_id).first():
        db.session.add(TopicWatch(user_id=user_id, topic_id=topic_id))

# =========================
# Akcie
# =========================

@forum_bp.post("/create")
@login_required
def create():
    """Založenie novej témy (bez kategórií)."""
    nazov = (request.form.get("nazov") or "").strip()
    body  = (request.form.get("body") or "").strip()

    if not nazov:
        flash("Zadaj názov témy.", "warning")
        return redirect(url_for("komunita.hub", tab="forum"))

    # jednoduchý anti-spam: max 1 téma / 2 min
    two_min_ago = datetime.utcnow() - timedelta(minutes=2)
    recent = ForumTopic.query.filter(
        ForumTopic.autor_id == current_user.id,
        ForumTopic.vytvorene_at >= two_min_ago
    ).count()
    if recent:
        flash("Skús to prosím o chvíľu – aby sme predišli spamu.", "warning")
        return redirect(url_for("komunita.hub", tab="forum"))

    t = ForumTopic(
        nazov=nazov,
        body=body,
        autor_id=current_user.id,
        vytvorene_at=datetime.utcnow(),
        aktivita_at=datetime.utcnow(),
    )
    db.session.add(t)
    db.session.flush()  # aby mal t.id hneď k dispozícii

    # autor automaticky sleduje vlastnú tému
    _ensure_watch(current_user.id, t.id)

    db.session.commit()
    flash("Téma bola vytvorená.", "success")
    return redirect(url_for("komunita.hub", tab="forum", t=t.id))

@forum_bp.post("/<int:topic_id>/reply")
@login_required
def reply(topic_id: int):
    """Odoslanie odpovede v téme."""
    topic = ForumTopic.query.get_or_404(topic_id)

    # --- telo správy + @prefix ---------------------------------------------
    body = (request.form.get("body") or "").strip()
    target_name = (request.form.get("reply_to_name") or "").strip()

    if not body:
        flash("Napíš odpoveď.", "warning")
        return redirect(url_for("komunita.hub", tab="forum", t=topic.id))

    if target_name:
        prefix = f"@{target_name} "
        if not body.startswith(prefix):
            body = re.sub(r"^@\S+\s+", "", body)
            body = prefix + body

    # --- antispam / throttling (okrem admin/mod) ----------------------------
    if not (getattr(current_user, "is_admin", False) or getattr(current_user, "is_moderator", False)):
        now = datetime.utcnow()
        cooldown = 20  # sekúnd
        recent_cut = now - timedelta(seconds=cooldown)

        # stačí vedieť, či existuje niečo v okne; je to lacnejšie než count()
        last = (ForumPost.query
                .with_entities(ForumPost.vytvorene_at)
                .filter(
                    ForumPost.autor_id == current_user.id,
                    ForumPost.vytvorene_at >= recent_cut
                )
                .order_by(ForumPost.vytvorene_at.desc())
                .first())

        if last:
            remain = cooldown - int((now - last.vytvorene_at).total_seconds())
            if remain > 0:
                flash(f"Skús to prosím o chvíľu (antispam, ešte ~{remain}s).", "warning")
                return redirect(url_for("komunita.hub", tab="forum", t=topic.id))

        # mikro-ochrana proti dvojkliku: rovnaké telo v tej istej téme do 5s
        dup = (ForumPost.query
               .with_entities(ForumPost.id)
               .filter(
                   ForumPost.autor_id == current_user.id,
                   ForumPost.topic_id == topic.id,
                   ForumPost.body == body,
                   ForumPost.vytvorene_at >= (now - timedelta(seconds=5))
               )
               .first())
        if dup:
            flash("Zdá sa, že si to práve odoslal/a (zabránené duplicitnému odoslaniu).", "info")
            return redirect(url_for("komunita.hub", tab="forum", t=topic.id, _anchor=f"post-{dup.id}"))

    # --- uloženie odpovede --------------------------------------------------
    now = datetime.utcnow()
    p = ForumPost(
        body=body,
        autor_id=current_user.id,
        topic_id=topic.id,
        vytvorene_at=now,
    )
    topic.aktivita_at = now
    db.session.add(p)

    # pisateľ automaticky sleduje tému
    _ensure_watch(current_user.id, topic.id)

    try:
        db.session.commit()  # potrebujeme p.id
    except Exception:
        db.session.rollback()
        flash("Nepodarilo sa odoslať odpoveď. Skús to ešte raz.", "warning")
        return redirect(url_for("komunita.hub", tab="forum", t=topic.id))

    # --- notifikácie (autor témy, watcheri, mentions) -----------------------
    create_forum_notifications(p, topic, current_user.id)

    return redirect(url_for("komunita.hub", tab="forum", t=topic.id, _anchor=f"post-{p.id}"))


@forum_bp.post("/<int:post_id>/mark-best")
@login_required
def mark_best(post_id: int):
    """Označenie odpovede ako najlepšej (len autor témy / mod / admin)."""
    p = ForumPost.query.get_or_404(post_id)
    topic = ForumTopic.query.get_or_404(p.topic_id)

    if topic.autor_id != current_user.id and not getattr(current_user, "is_moderator", False) and not getattr(current_user, "is_admin", False):
        abort(403)

    # zruš existujúcu „naj“ odpoveď v téme
    ForumPost.query.filter_by(topic_id=topic.id, is_answer=True).update({"is_answer": False})
    p.is_answer = True
    topic.aktivita_at = datetime.utcnow()
    db.session.commit()

    flash("Odpoveď označená ako najlepšia.", "success")
    return redirect(url_for("komunita.hub", tab="forum", t=topic.id, _anchor=f"post-{p.id}"))

@forum_bp.post("/<int:topic_id>/toggle-watch")
@login_required
def toggle_watch(topic_id: int):
    """Zapnúť/vypnúť sledovanie témy."""
    ForumTopic.query.get_or_404(topic_id)  # validácia existencie
    now_watching = _toggle_watch(current_user.id, topic_id)
    db.session.commit()

    flash("Téma pridaná do sledovaných." if now_watching else "Sledovanie zrušené.", "info")
    # vráť sa späť do toho istého detailu (ak je), inak na forum tab
    return redirect(request.referrer or url_for("komunita.hub", tab="forum", t=topic_id))

# =========================
# Navigačné skratky
# =========================

@forum_bp.route('/')
def index():
    """Skratka z ikonky – priamo na fórum (tab)."""
    try:
        return redirect(url_for('komunita.hub', tab='forum') + '#tab-forum')
    except BuildError:
        try:
            return redirect(url_for('main.index') + '#tab-forum')
        except BuildError:
            return '/'

@forum_bp.route('/unread')
@login_required
def goto_unread():
    """Ak existuje neprečítané, skoč na najnovšiu neprečítanú odpoveď; inak len na fórum."""
    try:
        from models import ForumNotification  # lazy import
    except Exception:
        return redirect(url_for('komunita.hub', tab='forum') + '#tab-forum')

    n = (ForumNotification.query
         .filter_by(user_id=current_user.id, read_at=None)
         .order_by(ForumNotification.created_at.desc())
         .first())
    if not n:
        return redirect(url_for('komunita.hub', tab='forum') + '#tab-forum')

    # označ ako prečítané hneď (alebo to nechaj na komunita.hub pri zobrazení detailu)
    n.read_at = datetime.utcnow()
    db.session.commit()

    return redirect(url_for('komunita.hub', tab='forum', t=n.topic_id, _anchor=f'post-{n.post_id}'))

# =========================
# Notifikácie (reply / watch / @mention)
# =========================

MENTION_RE = re.compile(r'@([A-Za-z0-9_.-]{2,32})')

def create_forum_notifications(post: ForumPost, topic: ForumTopic, author_id: int) -> None:
    try:
        from models import ForumNotification
    except Exception:
        return

    # priorita dôvodu: mention > reply > watch
    def better_reason(old, new):
        order = {'watch': 0, 'reply': 1, 'mention': 2}
        return new if order.get(new, -1) > order.get(old, -1) else old

    recipients = {}  # user_id -> best reason

    # 1) autor témy
    if getattr(topic, 'autor_id', None) and topic.autor_id != author_id:
        recipients[topic.autor_id] = better_reason(recipients.get(topic.autor_id), 'reply')

    # 2) watcheri
    try:
        for w in TopicWatch.query.filter_by(topic_id=topic.id).all():
            if w.user_id != author_id:
                recipients[w.user_id] = better_reason(recipients.get(w.user_id), 'watch')
    except Exception:
        pass

    # 3) mentions
    usernames = set(MENTION_RE.findall((getattr(post, 'body', None) or '')))
    if usernames:
        users = Pouzivatel.query.filter(Pouzivatel.prezyvka.in_(list(usernames))).all()
        for u in users:
            if u.id != author_id:
                recipients[u.id] = better_reason(recipients.get(u.id), 'mention')

    if not recipients:
        return

    for uid, reason in recipients.items():
        db.session.add(ForumNotification(
            user_id=uid, topic_id=topic.id, post_id=post.id, reason=reason
        ))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

@forum_bp.post('/mark-all-read')
@login_required
def mark_all_read():
    try:
        from models import ForumNotification
        ForumNotification.query.filter_by(user_id=current_user.id, read_at=None)\
                               .update({'read_at': datetime.utcnow()})
        db.session.commit()
        flash("Všetko označené ako prečítané.", "success")
    except Exception:
        db.session.rollback()
        flash("Nepodarilo sa označiť notifikácie.", "warning")
    return redirect(request.referrer or url_for('komunita.hub', tab='forum') + '#tab-forum')


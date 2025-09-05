# modules/forum.py
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, ForumCategory, ForumTopic, ForumPost, TopicWatch  # uprav cestu ak máš inak

forum_bp = Blueprint("forum", __name__, template_folder="../templates")

def _watched_ids_for(user_id: int):
    if not user_id:
        return set()
    rows = TopicWatch.query.filter_by(user_id=user_id).all()
    return {r.topic_id for r in rows}

@forum_bp.route("/", methods=["GET"])
def index():
    kategoria_id = request.args.get("kategoria", type=int)
    sort = request.args.get("sort", "activity")

    q = ForumTopic.query
    if kategoria_id:
        q = q.filter(ForumTopic.kategoria_id == kategoria_id)

    if sort == "newest":
        q = q.order_by(ForumTopic.vytvorene_at.desc())
    elif sort == "answers":
        # nateraz poradie podľa aktivity; agregáciu dorobíme neskôr
        q = q.order_by(ForumTopic.aktivita_at.desc())
    else:
        q = q.order_by(ForumTopic.aktivita_at.desc())

    topics = q.limit(50).all()
    categories = ForumCategory.query.order_by(ForumCategory.nazov.asc()).all()

    selected_id = request.args.get("t", type=int)
    selected_topic = ForumTopic.query.get(selected_id) if selected_id else None

    watched_ids = _watched_ids_for(current_user.id) if getattr(current_user, "is_authenticated", False) else set()

    return render_template(
        "komunita_forum.html",
        categories=categories,
        topics=topics,
        selected_topic=selected_topic,
        watched_ids=watched_ids,
    )

@forum_bp.route("/tema/<int:topic_id>", methods=["GET"])
def topic(topic_id: int):
    selected_topic = ForumTopic.query.get_or_404(topic_id)
    topics = ForumTopic.query.order_by(ForumTopic.aktivita_at.desc()).limit(50).all()
    categories = ForumCategory.query.order_by(ForumCategory.nazov.asc()).all()
    watched_ids = _watched_ids_for(current_user.id) if getattr(current_user, "is_authenticated", False) else set()

    return render_template(
        "komunita_forum.html",
        categories=categories,
        topics=topics,
        selected_topic=selected_topic,
        watched_ids=watched_ids,
    )

@forum_bp.route("/nova", methods=["POST"])
@login_required
def create():
    nazov = (request.form.get("nazov") or "").strip()
    body = (request.form.get("body") or "").strip()
    kategoria_id = request.form.get("kategoria_id", type=int)

    if not nazov or not body or not kategoria_id:
        flash("Vyplň nadpis, text aj kategóriu.", "warning")
        return redirect(url_for("forum.index"))

    topic = ForumTopic(
        nazov=nazov,
        body=body,
        autor_id=current_user.id,
        kategoria_id=kategoria_id,
        vytvorene_at=datetime.utcnow(),
        aktivita_at=datetime.utcnow(),
    )
    db.session.add(topic)
    db.session.flush()  # aby mal topic.id

    # auto-sledovanie autora témy
    if not TopicWatch.query.get((current_user.id, topic.id)):
        db.session.add(TopicWatch(user_id=current_user.id, topic_id=topic.id))

    db.session.commit()

    flash("Téma bola vytvorená.", "success")
    return redirect(url_for("forum.topic", topic_id=topic.id))

@forum_bp.route("/tema/<int:topic_id>/odpoved", methods=["POST"])
@login_required
def reply(topic_id: int):
    topic = ForumTopic.query.get_or_404(topic_id)
    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Napíš odpoveď.", "warning")
        return redirect(url_for("forum.topic", topic_id=topic.id))

    post = ForumPost(
        body=body,
        autor_id=current_user.id,
        topic_id=topic.id,
        vytvorene_at=datetime.utcnow(),
    )
    topic.aktivita_at = datetime.utcnow()
    db.session.add(post)

    # auto-sledovanie pri odpovedi
    if not TopicWatch.query.get((current_user.id, topic.id)):
        db.session.add(TopicWatch(user_id=current_user.id, topic_id=topic.id))

    db.session.commit()
    return redirect(url_for("forum.topic", topic_id=topic.id) + f"#post-{post.id}")

@forum_bp.route("/odpoved/<int:post_id>/best", methods=["POST"])
@login_required
def mark_best(post_id: int):
    post = ForumPost.query.get_or_404(post_id)
    topic = post.topic
    # len autor témy alebo moderátor/admin
    if topic.autor_id != current_user.id and not getattr(current_user, "is_moderator", False) and not getattr(current_user, "is_admin", False):
        abort(403)

    # zruš starú naj odpoveď, ak je
    for p in topic.posts:
        if p.is_answer:
            p.is_answer = False
    post.is_answer = True
    topic.aktivita_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("forum.topic", topic_id=topic.id) + f"#post-{post.id}")

@forum_bp.route("/tema/<int:topic_id>/watch", methods=["POST"])
@login_required
def toggle_watch(topic_id: int):
    topic = ForumTopic.query.get_or_404(topic_id)
    tw = TopicWatch.query.get((current_user.id, topic_id))
    if tw:
        db.session.delete(tw)
        flash("Zrušené sledovanie témy.", "info")
    else:
        db.session.add(TopicWatch(user_id=current_user.id, topic_id=topic_id))
        flash("Téma pridaná do sledovaných.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("forum.topic", topic_id=topic_id))

import io
import os
import time
from collections import OrderedDict

import requests as http
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

import json

from models import db, Setting, ScanJob, Frame, Item, Feedback
from pipeline import (DATA_DIR, UPLOADS_DIR, FRAMES_DIR, start_worker,
                      enqueue, delete_job_files)
from providers import DEFAULT_MODELS, PROVIDER_LABELS

APP_VERSION = "1.1"
ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

app = Flask(__name__)
# Honour X-Forwarded-Prefix so url_for() emits the mount path when this runs
# behind a proxy that strips one (e.g. /scan in SWSuite). No effect when the
# header is absent, so running standalone is unchanged.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(DATA_DIR, 'swscan.db')}"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB uploads
db.init_app(app)

for d in (DATA_DIR, UPLOADS_DIR, FRAMES_DIR):
    os.makedirs(d, exist_ok=True)

def _migrate():
    """Lightweight SQLite migration: add columns introduced after v1.0."""
    from sqlalchemy import text
    cols = {r[1] for r in db.session.execute(text("PRAGMA table_info(item)"))}
    if "verified" not in cols:
        db.session.execute(text(
            "ALTER TABLE item ADD COLUMN verified VARCHAR(16) DEFAULT 'unverified'"))
    if "box" not in cols:
        db.session.execute(text("ALTER TABLE item ADD COLUMN box TEXT DEFAULT ''"))
    db.session.commit()


with app.app_context():
    db.create_all()
    _migrate()
start_worker(app)


@app.context_processor
def inject_globals():
    return {"APP_VERSION": APP_VERSION, "PROVIDER_LABELS": PROVIDER_LABELS}


# ------------------------------------------------------------- control panel

@app.route("/")
def dashboard():
    jobs = ScanJob.query.order_by(ScanJob.created.desc()).limit(8).all()
    stats = {
        "total_items": Item.query.count(),
        "jobs": ScanJob.query.count(),
        "categories": db.session.query(Item.category).distinct().count(),
        "zones": db.session.query(Item.zone).filter(Item.zone != "").distinct().count(),
        "confirmed": Item.query.filter_by(verified="confirmed").count(),
        "feedback": Feedback.query.count(),
    }
    provider = Setting.get("provider", "anthropic")
    keys = {p: bool(Setting.get(f"{p}_api_key")) for p in DEFAULT_MODELS}
    return render_template("dashboard.html", jobs=jobs, stats=stats,
                           provider=provider, keys=keys)


# ------------------------------------------------------------------- scanning

@app.route("/scan", methods=["GET", "POST"])
def scan():
    if request.method == "POST":
        f = request.files.get("video")
        if not f or os.path.splitext(f.filename)[1].lower() not in ALLOWED_EXT:
            return render_template("scan.html", error="Upload a video file (mp4/mov/mkv/avi/webm)."), 400
        provider = request.form.get("provider") or Setting.get("provider", "anthropic")
        if not Setting.get(f"{provider}_api_key"):
            return render_template("scan.html",
                                   error=f"No API key set for {PROVIDER_LABELS[provider]}. Add one in Settings."), 400
        name = f"{int(time.time())}_{secure_filename(f.filename)}"
        f.save(os.path.join(UPLOADS_DIR, name))
        job = ScanJob(filename=name, zone=request.form.get("zone", "").strip(),
                      provider=provider,
                      model=request.form.get("model", "").strip() or DEFAULT_MODELS[provider])
        db.session.add(job)
        db.session.commit()
        enqueue(job.id)
        return redirect(url_for("job_detail", job_id=job.id))
    return render_template("scan.html",
                           provider=Setting.get("provider", "anthropic"),
                           defaults=DEFAULT_MODELS)


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = db.session.get(ScanJob, job_id) or abort(404)
    frames = Frame.query.filter_by(job_id=job_id, selected=True).order_by(Frame.idx).all()
    items = Item.query.filter_by(job_id=job_id).order_by(Item.category, Item.name).all()
    boxes = {}
    for it in items:
        if it.box and it.frame_id:
            b = json.loads(it.box)
            boxes.setdefault(it.frame_id, []).append(
                {"name": it.name, "l": b[0] / 10, "t": b[1] / 10,
                 "w": (b[2] - b[0]) / 10, "h": (b[3] - b[1]) / 10})
    return render_template("job.html", job=job, frames=frames, items=items, boxes=boxes)


@app.route("/api/jobs/<int:job_id>")
def job_status(job_id):
    job = db.session.get(ScanJob, job_id) or abort(404)
    return jsonify(status=job.status, progress=job.progress,
                   frames_total=job.frames_total,
                   frames_analyzed=job.frames_analyzed, message=job.message)


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def job_delete(job_id):
    job = db.session.get(ScanJob, job_id) or abort(404)
    Item.query.filter_by(job_id=job_id).update({"job_id": None, "frame_id": None})
    db.session.delete(job)
    db.session.commit()
    delete_job_files(job_id)
    try:
        os.remove(os.path.join(UPLOADS_DIR, job.filename))
    except OSError:
        pass
    return redirect(url_for("dashboard"))


# -------------------------------------------------------------------- catalog

@app.route("/catalog")
def catalog():
    q = request.args.get("q", "").strip()
    group_by = request.args.get("group", "category")  # category | zone
    query = Item.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Item.name.ilike(like), Item.notes.ilike(like),
                                    Item.category.ilike(like), Item.zone.ilike(like)))
    items = query.order_by(Item.category, Item.name).all()
    groups = OrderedDict()
    for it in items:
        key = (it.zone or "unzoned") if group_by == "zone" else (it.category or "uncategorised")
        groups.setdefault(key, []).append(it)
    return render_template("catalog.html", groups=groups, q=q, group_by=group_by,
                           total=len(items))


@app.route("/review")
def review():
    """Slideshow: step through unverified detected items and confirm/reject."""
    scope = request.args.get("scope", "unverified")  # unverified | all
    q = Item.query.filter(Item.job_id.isnot(None))
    if scope == "unverified":
        q = q.filter(Item.verified == "unverified")
    items = q.order_by(Item.job_id.desc(), Item.category, Item.name).all()
    total_unverified = Item.query.filter(
        Item.job_id.isnot(None), Item.verified == "unverified").count()
    return render_template("review.html", items=items, scope=scope,
                           total_unverified=total_unverified)


@app.route("/api/items/<int:item_id>")
def item_json(item_id):
    it = db.session.get(Item, item_id) or abort(404)
    if it.image_path and it.box:
        img = url_for("item_boxed", item_id=it.id)
    elif it.image_path:
        img = url_for("media", relpath=it.image_path)
    else:
        img = it.image_url or ""
    return jsonify(id=it.id, name=it.name, category=it.category,
                   quantity=it.quantity, condition=it.condition,
                   zone=it.zone, verified=it.verified, image=img)


@app.route("/api/items/<int:item_id>/verdict", methods=["POST"])
def item_verdict(item_id):
    """JSON verdict endpoint for the review slideshow (confirm/reject/rename)."""
    it = db.session.get(Item, item_id) or abort(404)
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    new_name = (data.get("name") or "").strip()
    if action == "confirm":
        if new_name and new_name != it.name:
            db.session.add(Feedback(action="rename", original_name=it.name,
                                    corrected_name=new_name, category=it.category))
            it.name = new_name
        else:
            db.session.add(Feedback(action="confirm", original_name=it.name,
                                    category=it.category))
        it.verified = "confirmed"
    elif action == "reject":
        db.session.add(Feedback(action="reject", original_name=it.name,
                                category=it.category))
        it.verified = "rejected"
    else:
        return jsonify(error="bad action"), 400
    db.session.commit()
    return jsonify(ok=True, verified=it.verified)


@app.route("/items/new", methods=["POST"])
def item_new():
    it = Item(name=request.form.get("name", "New item"),
              category=request.form.get("category", "other"),
              quantity=request.form.get("quantity", "1"),
              zone=request.form.get("zone", ""))
    db.session.add(it)
    db.session.commit()
    return redirect(url_for("item_detail", item_id=it.id))


@app.route("/items/<int:item_id>", methods=["GET", "POST"])
def item_detail(item_id):
    it = db.session.get(Item, item_id) or abort(404)
    if request.method == "POST":
        new_name = request.form.get("name", it.name).strip()
        if it.job_id and new_name and new_name != it.name:
            db.session.add(Feedback(action="rename", original_name=it.name,
                                    corrected_name=new_name, category=it.category))
            it.verified = "confirmed"
        for field in ("name", "category", "quantity", "condition", "zone", "notes", "image_url"):
            setattr(it, field, request.form.get(field, getattr(it, field)))
        db.session.commit()
        return redirect(url_for("item_detail", item_id=it.id))
    frames = Frame.query.filter_by(job_id=it.job_id, selected=True).all() if it.job_id else []
    return render_template("item.html", item=it, frames=frames)


@app.route("/items/<int:item_id>/delete", methods=["POST"])
def item_delete(item_id):
    it = db.session.get(Item, item_id) or abort(404)
    db.session.delete(it)
    db.session.commit()
    return redirect(url_for("catalog"))


@app.route("/items/<int:item_id>/verify", methods=["POST"])
def item_verify(item_id):
    it = db.session.get(Item, item_id) or abort(404)
    action = request.form.get("action")
    if action in ("confirm", "reject"):
        it.verified = "confirmed" if action == "confirm" else "rejected"
        db.session.add(Feedback(action=action, original_name=it.name,
                                category=it.category))
        db.session.commit()
    return redirect(request.referrer or url_for("item_detail", item_id=item_id))


@app.route("/items/<int:item_id>/set-image", methods=["POST"])
def item_set_image(item_id):
    it = db.session.get(Item, item_id) or abort(404)
    frame = db.session.get(Frame, int(request.form["frame_id"]))
    if frame:
        it.image_path = frame.path
        it.image_url = ""
        db.session.commit()
    return redirect(url_for("item_detail", item_id=it.id))


# ----------------------------------------------------------------- find images

@app.route("/api/items/<int:item_id>/find-images")
def find_images(item_id):
    it = db.session.get(Item, item_id) or abort(404)
    base = Setting.get("searxng_url").rstrip("/")
    if not base:
        return jsonify(error="No SearXNG URL configured in Settings."), 400
    try:
        r = http.get(f"{base}/search",
                     params={"q": it.name, "categories": "images", "format": "json"},
                     timeout=15)
        r.raise_for_status()
        results = [{"url": x.get("img_src"), "title": x.get("title"),
                    "source": x.get("url")}
                   for x in r.json().get("results", [])[:12] if x.get("img_src")]
        return jsonify(results=results)
    except Exception as e:  # noqa: BLE001
        return jsonify(error=str(e)), 502


# --------------------------------------------------- item image with bbox

@app.route("/items/<int:item_id>/boxed.jpg")
def item_boxed(item_id):
    """Serve the item's source frame with its bounding box drawn on."""
    from PIL import Image, ImageDraw
    it = db.session.get(Item, item_id) or abort(404)
    if not (it.image_path and it.box):
        abort(404)
    path = os.path.join(DATA_DIR, it.image_path)
    if not os.path.exists(path):
        abort(404)
    img = Image.open(path).convert("RGB")
    w, h = img.size
    b = json.loads(it.box)
    box_px = [b[0] / 1000 * w, b[1] / 1000 * h, b[2] / 1000 * w, b[3] / 1000 * h]
    draw = ImageDraw.Draw(img)
    for off in range(3):  # 3px accent outline
        draw.rectangle([box_px[0] - off, box_px[1] - off,
                        box_px[2] + off, box_px[3] + off], outline=(90, 167, 232))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return send_file(buf, mimetype="image/jpeg")


# -------------------------------------------------------------------- gallery

@app.route("/gallery")
def gallery():
    job_id = request.args.get("job", type=int)
    query = Frame.query.filter_by(selected=True)
    if job_id:
        query = query.filter_by(job_id=job_id)
    frames = query.order_by(Frame.job_id.desc(), Frame.idx).limit(200).all()
    jobs = ScanJob.query.order_by(ScanJob.created.desc()).all()
    return render_template("gallery.html", frames=frames, jobs=jobs, job_id=job_id)


@app.route("/media/<path:relpath>")
def media(relpath):
    return send_from_directory(DATA_DIR, relpath)


# ------------------------------------------------------------------- settings

@app.route("/settings", methods=["GET", "POST"])
def settings():
    fields = ["provider", "anthropic_api_key", "openai_api_key", "gemini_api_key",
              "anthropic_model", "openai_model", "gemini_model",
              "searxng_url", "scene_threshold", "max_frames", "dedupe_distance"]
    if request.method == "POST":
        for f in fields:
            if f in request.form:
                Setting.set(f, request.form[f].strip())
        return redirect(url_for("settings"))
    vals = {f: Setting.get(f) for f in fields}
    vals["provider"] = vals["provider"] or "anthropic"
    return render_template("settings.html", vals=vals, defaults=DEFAULT_MODELS)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7734)), debug=False)

"""Background scan pipeline.

Video -> ffmpeg scene-change frame extraction -> dHash dedupe ->
vision provider -> grouped Items in the catalog.
"""
import os
import glob
import queue
import shutil
import subprocess
import threading

from PIL import Image

import json

from models import db, ScanJob, Frame, Item, Setting, Feedback
from providers import analyze_frame, DEFAULT_MODELS

job_queue = queue.Queue()
_worker_started = False

DATA_DIR = os.environ.get("SWSCAN_DATA", os.path.join(os.path.dirname(__file__), "data"))
FRAMES_DIR = os.path.join(DATA_DIR, "frames")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")


# ---------------------------------------------------------------- frame tools

def dhash(image, size=8):
    """Difference hash, Pillow-only. Returns hex string."""
    img = image.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(img.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _run_ffmpeg(args):
    """Run ffmpeg, raising with the actual stderr tail on failure."""
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-4:]
        raise RuntimeError("ffmpeg failed: " + " | ".join(tail))


def extract_frames(video_path, out_dir, scene_threshold=0.30, max_frames=60):
    """Scene-change extraction with an fps fallback if the video is too static.

    Notes:
    - -fps_mode replaces the removed -vsync flag (gone in ffmpeg 7+)
    - format=yuv420p forces 8-bit for JPEG output (Pixel/HDR footage is 10-bit HEVC)
    - out_range=full + -strict unofficial: newer ffmpeg mjpeg rejects limited-range YUV
    """
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, "f_%04d.jpg")
    _run_ffmpeg(
        ["ffmpeg", "-y", "-i", video_path,
         "-vf", f"select='gt(scene,{scene_threshold})',scale=1280:-2:out_range=full,format=yuv420p",
         "-fps_mode", "vfr", "-strict", "unofficial", "-q:v", "3", pattern],
    )
    frames = sorted(glob.glob(os.path.join(out_dir, "f_*.jpg")))
    if len(frames) < 5:  # static footage: fall back to 1 frame every 2 seconds
        for f in frames:
            os.remove(f)
        _run_ffmpeg(
            ["ffmpeg", "-y", "-i", video_path,
             "-vf", "fps=0.5,scale=1280:-2:out_range=full,format=yuv420p",
             "-strict", "unofficial", "-q:v", "3", pattern],
        )
        frames = sorted(glob.glob(os.path.join(out_dir, "f_*.jpg")))
    return frames[:max_frames]


def dedupe(paths, max_distance=6):
    """Return [(path, hash, selected)] keeping only perceptually distinct frames."""
    kept_hashes, results = [], []
    for p in paths:
        with Image.open(p) as img:
            h = dhash(img)
        distinct = all(hamming(h, k) > max_distance for k in kept_hashes)
        if distinct:
            kept_hashes.append(h)
        results.append((p, h, distinct))
    return results


# ---------------------------------------------------------------- grouping

def normalise(name):
    return " ".join(name.lower().replace("-", " ").split())


def group_items(raw_items):
    """Merge duplicate detections across frames of one job.
    Same normalised name + category -> single item, keep the richest quantity."""
    grouped = {}
    for it in raw_items:
        key = (normalise(it["name"]), it["category"])
        if key in grouped:
            g = grouped[key]
            g["hits"] += 1
            # prefer a numeric-looking quantity over vague ones
            if it["quantity"].strip("~ ").isdigit() and not g["quantity"].strip("~ ").isdigit():
                g["quantity"] = it["quantity"]
        else:
            grouped[key] = {**it, "hits": 1}
    return list(grouped.values())


# ------------------------------------------------------------- learning

def build_learned_prompt():
    """Base prompt plus user feedback: confirmed vocabulary and corrections.
    This is how confirming/rejecting results 'trains' future scans."""
    from providers import PROMPT
    extra = []
    confirmed = [r[0] for r in db.session.query(Item.name)
                 .filter(Item.verified == "confirmed").distinct().limit(40)]
    if confirmed:
        extra.append("Items known to exist in this environment (prefer these exact "
                     "names when you see them): " + "; ".join(confirmed))
    renames = Feedback.query.filter_by(action="rename").order_by(
        Feedback.created.desc()).limit(25).all()
    if renames:
        extra.append("Past corrections from the user, apply them: " + "; ".join(
            f"'{f.original_name}' is actually '{f.corrected_name}'" for f in renames))
    rejects = [r[0] for r in db.session.query(Feedback.original_name)
               .filter(Feedback.action == "reject").distinct().limit(25)]
    if rejects:
        extra.append("The user rejected these past detections as wrong, be more "
                     "careful before reporting them: " + "; ".join(rejects))
    if not extra:
        return PROMPT
    return PROMPT + "\n\nContext from previous verified scans:\n" + "\n".join(extra)


# ---------------------------------------------------------------- worker

def process_job(app, job_id):
    with app.app_context():
        job = db.session.get(ScanJob, job_id)
        if not job:
            return
        try:
            job.status = "extracting"
            db.session.commit()

            video_path = os.path.join(UPLOADS_DIR, job.filename)
            out_dir = os.path.join(FRAMES_DIR, str(job.id))
            threshold = float(Setting.get("scene_threshold", "0.30"))
            max_frames = int(Setting.get("max_frames", "60"))
            paths = extract_frames(video_path, out_dir, threshold, max_frames)

            deduped = dedupe(paths, int(Setting.get("dedupe_distance", "6")))
            for i, (path, h, selected) in enumerate(deduped):
                db.session.add(Frame(job_id=job.id, idx=i,
                                     path=os.path.relpath(path, DATA_DIR),
                                     dhash=h, selected=selected))
            job.frames_total = sum(1 for _, _, s in deduped if s)
            job.status = "analyzing"
            db.session.commit()

            provider = job.provider
            api_key = Setting.get(f"{provider}_api_key")
            model = job.model or DEFAULT_MODELS[provider]
            prompt = build_learned_prompt()

            raw, errors = [], []
            frames = Frame.query.filter_by(job_id=job.id, selected=True).all()
            for fr in frames:
                with open(os.path.join(DATA_DIR, fr.path), "rb") as fh:
                    items, err = analyze_frame(fh.read(), provider, api_key, model, prompt)
                if err:
                    errors.append(err)
                for it in items:
                    it["_frame_id"] = fr.id
                    it["_frame_path"] = fr.path
                raw.extend(items)
                fr.analyzed = True
                job.frames_analyzed += 1
                db.session.commit()

            if not raw and errors:
                raise RuntimeError(errors[0])

            for g in group_items(raw):
                db.session.add(Item(
                    job_id=job.id, frame_id=g.get("_frame_id"),
                    name=g["name"], category=g["category"],
                    quantity=g["quantity"], condition=g["condition"],
                    zone=job.zone, image_path=g.get("_frame_path", ""),
                    box=json.dumps(g["box"]) if g.get("box") else "",
                    notes=f"Detected in {g['hits']} frame(s)",
                ))
            job.status = "complete"
            job.message = f"{len(group_items(raw))} distinct items from {job.frames_analyzed} frames" + \
                          (f" ({len(errors)} frame errors)" if errors else "")
            db.session.commit()
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            job = db.session.get(ScanJob, job_id)
            job.status = "failed"
            job.message = str(e)[:500]
            db.session.commit()


def worker_loop(app):
    while True:
        job_id = job_queue.get()
        try:
            process_job(app, job_id)
        finally:
            job_queue.task_done()


def start_worker(app):
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    t = threading.Thread(target=worker_loop, args=(app,), daemon=True)
    t.start()


def enqueue(job_id):
    job_queue.put(job_id)


def delete_job_files(job_id):
    shutil.rmtree(os.path.join(FRAMES_DIR, str(job_id)), ignore_errors=True)

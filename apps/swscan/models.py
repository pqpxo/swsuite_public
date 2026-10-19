from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class Setting(db.Model):
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, default="")

    @staticmethod
    def get(key, default=""):
        row = db.session.get(Setting, key)
        return row.value if row and row.value else default

    @staticmethod
    def set(key, value):
        row = db.session.get(Setting, key)
        if row:
            row.value = value
        else:
            db.session.add(Setting(key=key, value=value))
        db.session.commit()


class ScanJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    zone = db.Column(db.String(120), default="")
    provider = db.Column(db.String(32))
    model = db.Column(db.String(64))
    status = db.Column(db.String(32), default="queued")  # queued/extracting/analyzing/complete/failed
    message = db.Column(db.Text, default="")
    frames_total = db.Column(db.Integer, default=0)
    frames_analyzed = db.Column(db.Integer, default=0)
    created = db.Column(db.DateTime, default=utcnow)
    frames = db.relationship("Frame", backref="job", cascade="all, delete-orphan")
    items = db.relationship("Item", backref="job")

    @property
    def progress(self):
        if self.status == "complete":
            return 100
        if self.frames_total:
            return int(self.frames_analyzed / self.frames_total * 100)
        return 0


class Frame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("scan_job.id"))
    idx = db.Column(db.Integer)
    path = db.Column(db.String(255))
    dhash = db.Column(db.String(32))
    selected = db.Column(db.Boolean, default=True)   # survived dedupe, sent to provider
    analyzed = db.Column(db.Boolean, default=False)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("scan_job.id"), nullable=True)
    frame_id = db.Column(db.Integer, db.ForeignKey("frame.id"), nullable=True)
    name = db.Column(db.String(200))
    category = db.Column(db.String(100), default="uncategorised")  # "type" in the spec
    quantity = db.Column(db.String(40), default="1")               # allows "several", "~6"
    condition = db.Column(db.String(80), default="")
    zone = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    image_path = db.Column(db.String(255), default="")   # local frame/crop
    image_url = db.Column(db.String(500), default="")    # found via image search
    verified = db.Column(db.String(16), default="unverified")  # unverified/confirmed/rejected
    box = db.Column(db.Text, default="")  # JSON [x0,y0,x1,y1] normalised 0-1000
    created = db.Column(db.DateTime, default=utcnow)
    updated = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


class Feedback(db.Model):
    """User verdicts on AI detections, fed back into future scan prompts."""
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(16))          # confirm / reject / rename
    original_name = db.Column(db.String(200))
    corrected_name = db.Column(db.String(200), default="")
    category = db.Column(db.String(100), default="")
    created = db.Column(db.DateTime, default=utcnow)

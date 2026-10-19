## version 11
import io
import json
import os
import requests
import platform
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import qrcode
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from mini_qr_client import MiniQrRenderError, render_mini_qr_png
from flask_wtf import FlaskForm
from markupsafe import Markup, escape
from PIL import Image, ImageOps
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename
from wtforms import (
    BooleanField,
    DateField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import IPAddress, Length, Optional

from app_category_fields_support_v2 import (
    build_asset_custom_field_groups,
    build_form_custom_field_groups,
)
from category_field_seed_runtime_v1 import seed_category_fields_if_missing


try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover
    fcntl = None


Image.MAX_IMAGE_PIXELS = 50_000_000  # ~7000x7000 px; blocks decompression bomb attacks

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data"))).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIR / "inventory.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
PING_LOCK_PATH = DATA_DIR / ".ping_worker.lock"
THREE_UP_QR_OUTPUT_DIR = BASE_DIR / "static" / "generated" / "three_up_qr"
THREE_UP_QR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LABEL_PRINTER_API_URL = os.environ.get(
    "LABEL_PRINTER_API_URL",
    "http://x.x.x.x:5000/api/print",
)

THREE_UP_LABEL_WIDTH = 696
THREE_UP_LABEL_HEIGHT = 271
THREE_UP_QR_SIZE = 212
THREE_UP_SIDE_MARGIN = 18
THREE_UP_TOP_MARGIN = 26
THREE_UP_QR_GAP = 11

SVG_ALLOWED_TAGS = {
    "svg",
    "g",
    "path",
    "circle",
    "rect",
    "line",
    "polyline",
    "polygon",
    "ellipse",
    "defs",
    "linearGradient",
    "radialGradient",
    "stop",
    "title",
    "desc",
    "clipPath",
    "mask",
    "pattern",
    "symbol",
    "use",
}
SVG_ALLOWED_ATTRS = {
    "xmlns",
    "viewBox",
    "width",
    "height",
    "fill",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "d",
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "points",
    "transform",
    "opacity",
    "fill-opacity",
    "stroke-opacity",
    "class",
    "id",
    "preserveAspectRatio",
    "offset",
    "stop-color",
    "stop-opacity",
    "gradientUnits",
    "gradientTransform",
    "clip-path",
    "mask",
    "version",
    "href",
    "{http://www.w3.org/1999/xlink}href",
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db = SQLAlchemy(app)
_ping_thread_started = False
_ping_lock_handle = None


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(16), nullable=True)
    icon_svg = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(24), nullable=True)
    assets = db.relationship("Asset", backref="category", lazy=True)


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_key = db.Column(
        db.String(32),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: uuid.uuid4().hex[:12],
    )
    name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    subcategory = db.Column(db.String(120), nullable=True)
    hidden_groups = db.Column(db.Text, nullable=True)
    parent_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=True)

    brand = db.Column(db.String(120), nullable=True)
    model = db.Column(db.String(120), nullable=True)
    hostname = db.Column(db.String(120), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    domain_url = db.Column(db.String(500), nullable=True)
    use_case = db.Column(db.Text, nullable=True)
    serial_number = db.Column(db.String(120), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    related_urls = db.Column(db.Text, nullable=True)

    requires_attention = db.Column(db.Boolean, default=False, nullable=False)
    requires_update = db.Column(db.Boolean, default=False, nullable=False)
    ping_enabled = db.Column(db.Boolean, default=False, nullable=False)
    ping_interval_minutes = db.Column(db.Integer, default=5, nullable=False)
    last_ping_status = db.Column(db.String(32), nullable=True)
    last_ping_checked_at = db.Column(db.DateTime, nullable=True)

    date_purchased = db.Column(db.Date, nullable=True)
    date_installed = db.Column(db.Date, nullable=True)
    date_repaired = db.Column(db.Date, nullable=True)
    date_fixed = db.Column(db.Date, nullable=True)
    retire_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    parent_asset = db.relationship("Asset", remote_side=[id], backref="children", lazy=True)
    photos = db.relationship(
        "AssetPhoto",
        backref="asset",
        cascade="all, delete-orphan",
        lazy=True,
    )
    custom_values = db.relationship(
        "CustomFieldValue",
        backref="asset",
        cascade="all, delete-orphan",
        lazy=True,
    )
    change_logs = db.relationship(
        "AssetChangeLog",
        backref="asset",
        cascade="all, delete-orphan",
        order_by="AssetChangeLog.changed_at.desc()",
        lazy=True,
    )


class AssetChangeLog(db.Model):
    __tablename__ = "asset_change_log"
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    changed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AssetPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PingHistory(db.Model):
    __tablename__ = "ping_history"
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    status = db.Column(db.String(16), nullable=False)
    checked_at = db.Column(db.DateTime, nullable=False, index=True)


class AppSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=True)


class CustomFieldDefinition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    label = db.Column(db.String(120), nullable=False)
    field_type = db.Column(db.String(20), nullable=False, default="text")
    placeholder = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    values = db.relationship(
        "CustomFieldValue",
        backref="field",
        cascade="all, delete-orphan",
        lazy=True,
    )


class CustomFieldValue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    field_id = db.Column(db.Integer, db.ForeignKey("custom_field_definition.id"), nullable=False)
    value = db.Column(db.Text, nullable=True)


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[Length(max=120)])
    description = TextAreaField("Description", validators=[Optional()])
    icon = StringField("Icon", validators=[Optional(), Length(max=16)])
    icon_svg = TextAreaField("SVG code", validators=[Optional()])
    color = StringField("Color", validators=[Optional(), Length(max=24)])
    submit = SubmitField("Save category")


class AssetForm(FlaskForm):
    name = StringField("Name", validators=[Length(max=200)])
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    parent_asset_id = SelectField("Parent / Upstream item", coerce=int, validators=[Optional()])

    brand = StringField("Brand", validators=[Optional(), Length(max=120)])
    model = StringField("Model", validators=[Optional(), Length(max=120)])
    hostname = StringField("Hostname", validators=[Optional(), Length(max=120)])
    ip_address = StringField("IP address", validators=[Optional(), IPAddress(ipv4=True, ipv6=True)])
    domain_url = StringField("Domain URL", validators=[Optional(), Length(max=500)])
    serial_number = StringField("Serial number", validators=[Optional(), Length(max=120)])
    location = StringField("Location", validators=[Optional(), Length(max=200)])
    ping_enabled = BooleanField("Enable Ping Check")
    ping_interval_minutes = StringField(
        "Ping interval (minutes)",
        validators=[Optional(), Length(max=4)],
    )

    date_purchased = DateField("Date purchased", validators=[Optional()], format="%Y-%m-%d")
    date_installed = DateField("Date installed", validators=[Optional()], format="%Y-%m-%d")
    date_repaired = DateField("Date repaired", validators=[Optional()], format="%Y-%m-%d")
    date_fixed = DateField("Date fixed", validators=[Optional()], format="%Y-%m-%d")
    retire_date = DateField("Retire date", validators=[Optional()], format="%Y-%m-%d")

    requires_attention = BooleanField("Requires Attention")
    requires_update = BooleanField("Requires Update")

    use_case = TextAreaField("Use / purpose", validators=[Optional()])
    related_urls = TextAreaField("Related URLs", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])

    submit = SubmitField("Save asset")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return value[:80] or f"field_{uuid.uuid4().hex[:8]}"


def strip_namespace(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def sanitise_svg_markup(svg_text: str | None) -> str | None:
    if not svg_text:
        return None

    svg_text = svg_text.strip()
    if not svg_text:
        return None

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return None

    if strip_namespace(root.tag) != "svg":
        return None

    def clean_element(element):
        tag_name = strip_namespace(element.tag)
        if tag_name not in SVG_ALLOWED_TAGS:
            return None

        clean_attrs = {}
        for attr_name, attr_value in element.attrib.items():
            plain_name = strip_namespace(attr_name)

            if attr_name not in SVG_ALLOWED_ATTRS and plain_name not in SVG_ALLOWED_ATTRS:
                continue

            if plain_name.startswith("on"):
                continue

            if plain_name in {"href"} and isinstance(attr_value, str):
                if attr_value and not attr_value.startswith("#"):
                    continue

            clean_attrs[attr_name] = attr_value

        new_element = ET.Element(tag_name, clean_attrs)
        if element.text and tag_name in {"title", "desc"}:
            new_element.text = element.text[:500]

        for child in list(element):
            cleaned_child = clean_element(child)
            if cleaned_child is not None:
                new_element.append(cleaned_child)

        return new_element

    cleaned_root = clean_element(root)
    if cleaned_root is None:
        return None

    if "xmlns" not in cleaned_root.attrib:
        cleaned_root.set("xmlns", "http://www.w3.org/2000/svg")

    return ET.tostring(cleaned_root, encoding="unicode")


def extract_svg_from_upload(file_storage) -> str | None:
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    filename = file_storage.filename.lower()
    if not filename.endswith(".svg"):
        return None

    raw = file_storage.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None

    return sanitise_svg_markup(text)


def category_icon_inner(category, default="📦"):
    if category and getattr(category, "icon_svg", None):
        return Markup(category.icon_svg)

    icon_value = default
    if category and getattr(category, "icon", None):
        icon_value = category.icon

    return Markup(escape(icon_value))


def normalise_url(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value

    if value.startswith("//"):
        return f"http:{value}"

    if "://" not in value:
        return f"http://{value}"

    return None


def formatted_related_urls(value: str | None) -> list[str]:
    if not value:
        return []

    items = []
    for line in value.splitlines():
        normalised = normalise_url(line)
        if normalised:
            items.append(normalised)
    return items


def get_setting(key: str, default: str | None = None) -> str | None:
    item = AppSetting.query.filter_by(key=key).first()
    if item and item.value is not None:
        return item.value
    return default


def set_setting(key: str, value: str | None) -> None:
    item = AppSetting.query.filter_by(key=key).first()
    if item is None:
        item = AppSetting(key=key, value=value)
        db.session.add(item)
    else:
        item.value = value


def base_url() -> str:
    configured = get_setting("qr_base_url") or os.environ.get("APP_BASE_URL", "")
    if configured:
        return configured.rstrip("/")
    return request.url_root.rstrip("/")


def asset_public_url(asset: Asset) -> str:
    return f"{base_url()}{url_for('asset_detail', asset_key=asset.asset_key)}"


def asset_open_url(asset: Asset) -> str | None:
    return normalise_url(asset.domain_url) or normalise_url(asset.ip_address)
def build_public_static_url(filename: str) -> str:
    return f"{base_url()}{url_for('static', filename=filename)}"


def generate_qr_image_for_asset(asset: Asset) -> Image.Image:
    qr_target = asset_public_url(asset)

    try:
        qr_bytes = render_mini_qr_png(qr_target)
        image = Image.open(io.BytesIO(qr_bytes)).convert("RGBA")
    except MiniQrRenderError:
        fallback = qrcode.make(qr_target)
        buffer = io.BytesIO()
        fallback.save(buffer, format="PNG")
        buffer.seek(0)
        image = Image.open(buffer).convert("RGBA")

    return image


def create_three_up_qr_label(asset_ids: list[str]) -> dict:
    assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
    asset_map = {str(asset.id): asset for asset in assets}
    ordered_assets = [asset_map.get(str(asset_id)) for asset_id in asset_ids]

    if any(asset is None for asset in ordered_assets):
        raise ValueError("One or more selected assets could not be found.")

    canvas = Image.new(
        "RGBA",
        (THREE_UP_LABEL_WIDTH, THREE_UP_LABEL_HEIGHT),
        (255, 255, 255, 255),
    )

    for index, asset in enumerate(ordered_assets):
        qr_image = generate_qr_image_for_asset(asset)
        qr_image = qr_image.resize((THREE_UP_QR_SIZE, THREE_UP_QR_SIZE), Image.LANCZOS)

        x = THREE_UP_SIDE_MARGIN + (index * (THREE_UP_QR_SIZE + THREE_UP_QR_GAP))
        y = THREE_UP_TOP_MARGIN

        canvas.alpha_composite(qr_image, (x, y))

    filename = f"three_up_qr_{uuid.uuid4().hex[:12]}.png"
    output_path = THREE_UP_QR_OUTPUT_DIR / filename
    canvas.save(output_path, format="PNG")

    cutoff = time.time() - 3600
    for old_file in THREE_UP_QR_OUTPUT_DIR.glob("three_up_qr_*.png"):
        try:
            if old_file.stat().st_mtime < cutoff and old_file != output_path:
                old_file.unlink()
        except OSError:
            pass

    relative_static_path = f"generated/three_up_qr/{filename}"
    image_url = build_public_static_url(relative_static_path)

    return {
        "filename": filename,
        "output_path": str(output_path),
        "image_url": image_url,
    }


def safe_ping_interval(value) -> int:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = 5
    return max(1, min(minutes, 1440))


def run_ping(ip_address: str, timeout_seconds: int = 1) -> bool:
    if not ip_address:
        return False

    system_name = platform.system().lower()
    if system_name == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_seconds * 1000), ip_address]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout_seconds), ip_address]

    result = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def ping_due(asset: Asset, now_utc: datetime) -> bool:
    if not asset.ping_enabled or not asset.ip_address:
        return False

    interval = safe_ping_interval(asset.ping_interval_minutes)
    if asset.last_ping_checked_at is None:
        return True

    last_checked = asset.last_ping_checked_at
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=timezone.utc)
    return (now_utc - last_checked) >= timedelta(minutes=interval)


_ping_cleanup_counter = 0

def ping_worker_loop():
    global _ping_cleanup_counter
    while True:
        try:
            with app.app_context():
                now_utc = datetime.now(timezone.utc)
                assets = Asset.query.filter(
                    Asset.ping_enabled.is_(True),
                    Asset.ip_address.isnot(None),
                    Asset.ip_address != "",
                ).all()

                changed = False
                for asset in assets:
                    if not ping_due(asset, now_utc):
                        continue

                    ok = run_ping(asset.ip_address)
                    asset.last_ping_status = "active" if ok else "offline"
                    asset.last_ping_checked_at = now_utc
                    db.session.add(PingHistory(
                        asset_id=asset.id,
                        status=asset.last_ping_status,
                        checked_at=now_utc,
                    ))
                    changed = True

                # Prune history older than 30 days every ~100 cycles
                _ping_cleanup_counter += 1
                if _ping_cleanup_counter >= 100:
                    _ping_cleanup_counter = 0
                    cutoff = now_utc - timedelta(days=30)
                    PingHistory.query.filter(PingHistory.checked_at < cutoff).delete()

                if changed:
                    db.session.commit()

        except Exception as exc:  # pragma: no cover
            app.logger.exception("Ping worker error: %s", exc)

        time.sleep(30)


def can_start_ping_worker() -> bool:
    global _ping_lock_handle

    if fcntl is None:
        return True

    try:
        PING_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        _ping_lock_handle = open(PING_LOCK_PATH, "a+")
        fcntl.flock(_ping_lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def start_ping_worker():
    global _ping_thread_started

    if _ping_thread_started:
        return

    if not can_start_ping_worker():
        app.logger.info("Ping worker already running in another process.")
        return

    worker = threading.Thread(target=ping_worker_loop, daemon=True, name="asset-ping-worker")
    worker.start()
    _ping_thread_started = True


def asset_status(asset: Asset) -> str:
    if asset.retire_date and asset.retire_date <= date.today():
        return "Retired"

    if getattr(asset, "ping_enabled", False) and asset.ip_address:
        if asset.last_ping_status == "active":
            return "Online"
        if asset.last_ping_status == "offline":
            return "Offline"
        return "Checking"

    return "Unknown"


def save_uploaded_photos(asset: Asset, uploaded_files) -> None:
    for file in uploaded_files:
        if not file or not file.filename:
            continue
        if not allowed_file(file.filename):
            flash(f"Skipped unsupported file: {file.filename}", "warning")
            continue

        image = Image.open(file.stream)
        image = ImageOps.exif_transpose(image)
        image.thumbnail((1800, 1800))
        original_name = secure_filename(file.filename)
        stem = Path(original_name).stem[:100] or "image"
        has_alpha = (
            "A" in image.getbands()
            or image.mode in {"RGBA", "LA", "PA"}
            or "transparency" in image.info
        )

        if has_alpha:
            unique_name = f"{uuid.uuid4().hex}_{stem}.png"
            filepath = UPLOAD_DIR / unique_name
            image = image.convert("RGBA")
            image.save(filepath, format="PNG", optimize=True)
        else:
            unique_name = f"{uuid.uuid4().hex}_{stem}.jpg"
            filepath = UPLOAD_DIR / unique_name
            image = image.convert("RGB")
            image.save(filepath, format="JPEG", quality=88, optimize=True)

        db.session.add(AssetPhoto(asset=asset, filename=unique_name))


def get_asset_trail(asset: Asset) -> list[Asset]:
    trail = []
    current = asset
    visited: set[int] = set()
    while current and current.id not in visited:
        trail.append(current)
        visited.add(current.id)
        current = current.parent_asset
    return list(reversed(trail))


def is_descendant(candidate_parent: Asset | None, asset: Asset) -> bool:
    current = candidate_parent
    visited: set[int] = set()
    while current and current.id not in visited:
        if current.id == asset.id:
            return True
        visited.add(current.id)
        current = current.parent_asset
    return False


def _asset_snapshot(asset: Asset) -> dict:
    return {
        "Name": asset.name or "",
        "Category": asset.category.name if asset.category else "",
        "Brand": asset.brand or "",
        "Model": asset.model or "",
        "Serial number": asset.serial_number or "",
        "Location": asset.location or "",
        "Hostname": asset.hostname or "",
        "IP address": asset.ip_address or "",
        "Domain URL": asset.domain_url or "",
        "Ping monitoring": "Enabled" if asset.ping_enabled else "Disabled",
        "Requires attention": "Yes" if asset.requires_attention else "No",
        "Requires update": "Yes" if asset.requires_update else "No",
        "Retire date": str(asset.retire_date) if asset.retire_date else "",
        "Parent asset": asset.parent_asset.name if asset.parent_asset else "",
        "subcategory": asset.subcategory or "",
    }


def _record_asset_changes(asset: Asset, old_snap: dict, new_snap: dict) -> None:
    now = datetime.now(timezone.utc)
    for field, old_val in old_snap.items():
        new_val = new_snap.get(field, "")
        if old_val != new_val:
            db.session.add(AssetChangeLog(
                asset_id=asset.id,
                field_name=field,
                old_value=old_val or None,
                new_value=new_val or None,
                changed_at=now,
            ))


def populate_asset_choices(form: AssetForm, current_asset: Asset | None = None) -> None:
    categories = Category.query.order_by(Category.name.asc()).all()
    form.category_id.choices = [(0, "— No category —")] + [(c.id, c.name) for c in categories]

    network_cat = Category.query.filter(Category.name == "Network Equipment").first()
    assets = (
        Asset.query
        .filter(Asset.category_id == network_cat.id)
        .order_by(Asset.name.asc())
        .all()
        if network_cat else []
    )
    choices = [(0, "— No parent / root item —")]
    for item in assets:
        if current_asset and item.id == current_asset.id:
            continue
        choices.append((item.id, item.name))
    form.parent_asset_id.choices = choices


def distinct_asset_values(column) -> list[str]:
    values = [
        row[0]
        for row in db.session.query(column)
        .filter(column.isnot(None), column != "")
        .distinct()
        .order_by(column.asc())
        .all()
    ]
    return values


def custom_field_definitions() -> list[CustomFieldDefinition]:
    return CustomFieldDefinition.query.order_by(
        CustomFieldDefinition.sort_order.asc(),
        CustomFieldDefinition.label.asc(),
    ).all()


def custom_field_values_for_asset(asset: Asset | None) -> dict[int, str]:
    if asset is None:
        return {}
    return {value.field_id: value.value or "" for value in asset.custom_values}


def save_custom_field_values(asset: Asset, form_data) -> None:
    existing = {value.field_id: value for value in asset.custom_values}
    for field in custom_field_definitions():
        key = f"custom_{field.id}"
        if field.field_type == "checkbox":
            value = "1" if form_data.get(key) else "0"
        else:
            value = (form_data.get(key) or "").strip()

        row = existing.get(field.id)
        if row is None:
            row = CustomFieldValue(asset=asset, field=field)
            db.session.add(row)

        row.value = value or ("0" if field.field_type == "checkbox" else None)


def custom_field_pairs(asset: Asset) -> list[dict]:
    values = custom_field_values_for_asset(asset)
    pairs = []
    for field in custom_field_definitions():
        raw_value = values.get(field.id, "")
        if field.field_type == "checkbox":
            display_value = "Yes" if raw_value == "1" else "No"
        else:
            display_value = raw_value or "—"

        pairs.append(
            {
                "label": field.label,
                "type": field.field_type,
                "value": display_value,
                "raw": raw_value,
            }
        )
    return pairs


def parse_backup_zip(file_storage) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="inventory_restore_")).resolve()
    zip_path = temp_dir / "restore.zip"
    file_storage.save(zip_path)

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            member_path = (temp_dir / member.filename).resolve()
            if not str(member_path).startswith(str(temp_dir) + os.sep) and member_path != temp_dir:
                raise ValueError(f"Unsafe path in backup archive: {member.filename}")
            archive.extract(member, temp_dir)

    return temp_dir


def make_backup_bytes() -> io.BytesIO:
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if DATABASE_PATH.exists():
            archive.write(DATABASE_PATH, arcname="inventory.db")

        if UPLOAD_DIR.exists():
            for item in UPLOAD_DIR.rglob("*"):
                if item.is_file():
                    archive.write(item, arcname=str(Path("uploads") / item.relative_to(UPLOAD_DIR)))

    memory.seek(0)
    return memory


def ensure_schema() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS category ("
            "id INTEGER PRIMARY KEY, "
            "name VARCHAR(120) NOT NULL UNIQUE, "
            "description TEXT"
            ")"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS asset ("
            "id INTEGER PRIMARY KEY, asset_key VARCHAR(32) NOT NULL UNIQUE, name VARCHAR(200) NOT NULL, "
            "category_id INTEGER, parent_asset_id INTEGER, brand VARCHAR(120), model VARCHAR(120), "
            "hostname VARCHAR(120), ip_address VARCHAR(45), use_case TEXT, serial_number VARCHAR(120), "
            "location VARCHAR(200), notes TEXT, related_urls TEXT, date_purchased DATE, date_installed DATE, "
            "date_repaired DATE, date_fixed DATE, created_at DATETIME, updated_at DATETIME"
            ")"
        )

        def add_column_if_missing(table: str, column: str, definition: str) -> None:
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}
            if column not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        add_column_if_missing("category", "icon", "VARCHAR(16)")
        add_column_if_missing("category", "icon_svg", "TEXT")
        add_column_if_missing("category", "color", "VARCHAR(24)")
        add_column_if_missing("asset", "domain_url", "VARCHAR(500)")
        add_column_if_missing("asset", "requires_attention", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_if_missing("asset", "requires_update", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_if_missing("asset", "retire_date", "DATE")
        add_column_if_missing("asset", "ping_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_if_missing("asset", "ping_interval_minutes", "INTEGER NOT NULL DEFAULT 5")
        add_column_if_missing("asset", "last_ping_status", "VARCHAR(32)")
        add_column_if_missing("asset", "last_ping_checked_at", "DATETIME")

        # Check before adding so we can run the one-time migration
        cursor.execute("PRAGMA table_info(asset)")
        _existing_asset_cols = {row[1] for row in cursor.fetchall()}
        _subcategory_is_new = "subcategory" not in _existing_asset_cols
        add_column_if_missing("asset", "subcategory", "VARCHAR(120)")
        add_column_if_missing("asset", "hidden_groups", "TEXT")
        if _subcategory_is_new:
            cursor.execute("SELECT id FROM category WHERE LOWER(name) = 'servers'")
            _srv = cursor.fetchone()
            if _srv:
                cursor.execute("UPDATE asset SET category_id = NULL WHERE category_id = ?", (_srv[0],))

        cursor.execute(
            "CREATE TABLE IF NOT EXISTS ping_history ("
            "id INTEGER PRIMARY KEY, "
            "asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE, "
            "status VARCHAR(16) NOT NULL, "
            "checked_at DATETIME NOT NULL"
            ")"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_ping_history_checked_at "
            "ON ping_history (asset_id, checked_at)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS asset_change_log ("
            "id INTEGER PRIMARY KEY, "
            "asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE, "
            "field_name VARCHAR(100) NOT NULL, "
            "old_value TEXT, "
            "new_value TEXT, "
            "changed_at DATETIME NOT NULL"
            ")"
        )

        connection.commit()
    finally:
        connection.close()


def seed_defaults() -> None:
    defaults = [
        ("Network Equipment", "Routers, switches, access points and firewalls.", "🌐", "#4f8cff"),
        ("Servers", "Physical servers and virtualisation hosts.", "🖥️", "#6b85ff"),
        ("Single Board Computers", "Raspberry Pi and similar boards.", "🔧", "#60d394"),
        ("PCs & Workstations", "Desktop or laptop computers.", "💻", "#f0b35c"),
        ("Storage", "NAS, drives and storage accessories.", "💾", "#f0729e"),
        ("Peripherals", "Monitors, printers and accessories.", "🖨️", "#8f7cff"),
        ("Cables & Adapters", "Network, power and accessory cabling.", "🔌", "#7bc7ff"),
        ("Power", "PSUs, UPS units and power equipment.", "⚡", "#ff9f43"),
    ]
    for name, description, icon, color in defaults:
        category = Category.query.filter(func.lower(Category.name) == name.lower()).first()
        if category is None:
            db.session.add(Category(name=name, description=description, icon=icon, color=color))
        else:
            if not category.description:
                category.description = description
            if not category.icon:
                category.icon = icon
            if not category.color:
                category.color = color
    db.session.commit()


@app.template_filter("date_or_dash")
def date_or_dash(value):
    return value.strftime("%Y-%m-%d") if value else "—"


@app.context_processor
def inject_helpers():
    counts = dict(
        db.session.query(Asset.category_id, func.count(Asset.id))
        .group_by(Asset.category_id)
        .all()
    )
    sidebar_categories = [
        {"category": category, "asset_count": counts.get(category.id, 0)}
        for category in Category.query.order_by(Category.name.asc()).all()
    ]

    return {
        "formatted_related_urls": formatted_related_urls,
        "normalise_url": normalise_url,
        "asset_status": asset_status,
        "sidebar_total_assets": Asset.query.count(),
        "sidebar_categories": sidebar_categories,
        "category_icon_inner": category_icon_inner,
        "layout_mode": get_setting("layout_mode", "compact") or "compact",
        "three_up_qr_assets": Asset.query.order_by(Asset.name.asc()).all(),
        "label_printer_api_url": LABEL_PRINTER_API_URL,
        "sidebar_online": Asset.query.filter(
            Asset.ping_enabled.is_(True), Asset.last_ping_status == "active"
        ).count(),
        "sidebar_offline": Asset.query.filter(
            Asset.ping_enabled.is_(True), Asset.last_ping_status == "offline"
        ).count(),
        "sidebar_ping_enabled": Asset.query.filter(Asset.ping_enabled.is_(True)).count(),
    }


@app.route("/api/ping-statuses")
def api_ping_statuses():
    today = date.today()
    assets = Asset.query.with_entities(
        Asset.id,
        Asset.retire_date,
        Asset.ping_enabled,
        Asset.ip_address,
        Asset.last_ping_status,
    ).all()

    result = {}
    for a in assets:
        if a.retire_date and a.retire_date <= today:
            text, css = "Retired", "attention"
        elif a.ping_enabled and a.ip_address:
            if a.last_ping_status == "active":
                text, css = "Online", "active"
            elif a.last_ping_status == "offline":
                text, css = "Offline", "attention"
            else:
                text, css = "Checking", "update"
        else:
            text, css = "Unknown", "update"
        result[str(a.id)] = {"text": text, "css": css}

    return jsonify(result)


@app.route("/", methods=["GET"])
def index():
    query = request.args.get("q", "").strip()
    status = request.args.get("status", "all").strip() or "all"
    group_by = request.args.get("group_by", "none").strip() or "none"
    sort_by = request.args.get("sort_by", "name_asc").strip() or "name_asc"
    if group_by not in {"none", "category", "location", "brand", "status"}:
        group_by = "none"
    if sort_by not in {"name_asc", "name_desc", "status"}:
        sort_by = "name_asc"

    selected_category_id = request.args.get("category_id", type=int)

    asset_query = Asset.query
    if selected_category_id:
        asset_query = asset_query.filter(Asset.category_id == selected_category_id)

    if query:
        like = f"%{query}%"
        asset_query = asset_query.filter(
            or_(
                Asset.name.ilike(like),
                Asset.hostname.ilike(like),
                Asset.ip_address.ilike(like),
                Asset.domain_url.ilike(like),
                Asset.model.ilike(like),
                Asset.brand.ilike(like),
                Asset.location.ilike(like),
                Asset.related_urls.ilike(like),
            )
        )

    today = date.today()
    if status == "attention":
        asset_query = asset_query.filter(Asset.requires_attention.is_(True))
    elif status == "update":
        asset_query = asset_query.filter(Asset.requires_update.is_(True))
    elif status == "retired":
        asset_query = asset_query.filter(Asset.retire_date.isnot(None), Asset.retire_date <= today)
    elif status == "active":
        asset_query = asset_query.filter(
            Asset.ping_enabled.is_(True),
            Asset.ip_address.isnot(None),
            Asset.ip_address != "",
            Asset.last_ping_status == "active",
            or_(Asset.retire_date.is_(None), Asset.retire_date > today),
        )
    elif status == "offline":
        asset_query = asset_query.filter(
            Asset.ping_enabled.is_(True),
            Asset.last_ping_status == "offline",
        )

    if sort_by == "name_desc":
        assets = asset_query.order_by(Asset.name.desc()).all()
    elif sort_by == "status":
        _status_order = {"Online": 0, "Offline": 1, "Checking": 2, "Unknown": 3, "Retired": 4}
        assets = sorted(
            asset_query.order_by(Asset.name.asc()).all(),
            key=lambda a: (_status_order.get(asset_status(a), 99), a.name.lower()),
        )
    else:
        assets = asset_query.order_by(Asset.name.asc()).all()

    def group_label_for_asset(asset: Asset) -> str:
        if group_by == "category":
            return asset.category.name if asset.category else "Uncategorised"
        if group_by == "location":
            return asset.location or "No location"
        if group_by == "brand":
            return asset.brand or "No brand"
        if group_by == "status":
            return asset_status(asset)
        return "All assets"

    grouped_assets = []
    if group_by != "none":
        buckets: dict[str, list[Asset]] = {}
        for asset in assets:
            label = group_label_for_asset(asset)
            buckets.setdefault(label, []).append(asset)

        if group_by == "status":
            status_order = {
                "Online": 0,
                "Offline": 1,
                "Unknown": 2,
                "Checking": 3,
                "Retired": 4,
            }
            sorted_labels = sorted(buckets.keys(), key=lambda label: (status_order.get(label, 99), label.lower()))
        else:
            def sort_key(label: str):
                return (label.lower() in {"uncategorised", "no location", "no brand", "unknown"}, label.lower())

            sorted_labels = sorted(buckets.keys(), key=sort_key)

        grouped_assets = [{"label": label, "items": buckets[label]} for label in sorted_labels]

    today = date.today()
    _today = date.today()
    _ping_total = Asset.query.filter(
        Asset.ping_enabled.is_(True),
        Asset.ip_address.isnot(None),
        Asset.ip_address != "",
    ).count()
    _online = Asset.query.filter(Asset.ping_enabled.is_(True), Asset.last_ping_status == "active").count()
    _offline = Asset.query.filter(Asset.ping_enabled.is_(True), Asset.last_ping_status == "offline").count()
    _last_checked = db.session.query(func.max(Asset.last_ping_checked_at)).scalar()
    dash = {
        "total": Asset.query.count(),
        "online": _online,
        "offline": _offline,
        "attention": Asset.query.filter(Asset.requires_attention.is_(True)).count(),
        "needs_update": Asset.query.filter(Asset.requires_update.is_(True)).count(),
        "unknown": Asset.query.filter(
            or_(Asset.ping_enabled.is_(False), Asset.ip_address.is_(None), Asset.ip_address == ""),
            or_(Asset.retire_date.is_(None), Asset.retire_date > _today),
        ).count(),
        "uncategorised": Asset.query.filter(Asset.category_id.is_(None)).count(),
        "retired": Asset.query.filter(Asset.retire_date.isnot(None), Asset.retire_date <= _today).count(),
        "no_ip": Asset.query.filter(or_(Asset.ip_address.is_(None), Asset.ip_address == "")).count(),
        "ping_monitored": _ping_total,
        "ping_checking": max(0, _ping_total - _online - _offline),
        "last_checked_at": _last_checked,
    }

    return render_template(
        "index.html",
        assets=assets,
        query=query,
        status=status,
        group_by=group_by,
        sort_by=sort_by,
        grouped_assets=grouped_assets,
        selected_category_id=selected_category_id,
        all_categories=Category.query.order_by(Category.name.asc()).all(),
        dash=dash,
    )


@app.get("/api/assets/for-three-up-qr")
def api_assets_for_three_up_qr():
    assets = Asset.query.order_by(Asset.name.asc()).all()
    return jsonify([
        {
            "id": asset.id,
            "name": asset.name,
            "asset_key": asset.asset_key,
            "qr_url": url_for("asset_qr", asset_key=asset.asset_key),
        }
        for asset in assets
    ])

@app.post("/api/three-up-qr/generate")
def api_three_up_qr_generate():
    payload = request.get_json(silent=True) or {}
    asset_ids = payload.get("asset_ids") or []

    asset_ids = [str(x).strip() for x in asset_ids if str(x).strip()]

    if len(asset_ids) != 3:
        return jsonify({"ok": False, "error": "Please select exactly 3 assets."}), 400

    if len(set(asset_ids)) != 3:
        return jsonify({"ok": False, "error": "Please select 3 different assets."}), 400

    try:
        result = create_three_up_qr_label(asset_ids)
    except Exception as exc:
        app.logger.exception("3-up QR label generation failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(
        {
            "ok": True,
            "filename": result["filename"],
            "image_url": result["image_url"],
            "print_url": f"{LABEL_PRINTER_API_URL}?image_url={quote(result['image_url'], safe='')}",
        }
    )


@app.post("/api/three-up-qr/print")
def api_three_up_qr_print():
    if not LABEL_PRINTER_API_URL:
        return jsonify({"ok": False, "error": "Label printer URL is not configured. Set LABEL_PRINTER_API_URL in your environment."}), 503

    payload = request.get_json(silent=True) or {}
    image_url = (payload.get("image_url") or "").strip()

    if not image_url:
        return jsonify({"ok": False, "error": "image_url is required"}), 400

    try:
        response = requests.get(
            LABEL_PRINTER_API_URL,
            params={"image_url": image_url},
            timeout=30,
        )
        response.raise_for_status()
    except Exception as exc:
        app.logger.exception("3-up QR print request failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 502

    response_text = response.text.strip()
    return jsonify(
        {
            "ok": True,
            "message": "Label sent to printer successfully.",
            "printer_status": response.status_code,
            "printer_response": response_text,
            "requested_url": f"{LABEL_PRINTER_API_URL}?image_url={quote(image_url, safe='')}",
        }
    )

@app.route("/connections")
def connection_map():
    def _build_tree(asset):
        children = sorted(asset.children, key=lambda x: x.name.lower())
        return {
            "id": asset.id,
            "asset_key": asset.asset_key,
            "name": asset.name,
            "ip": asset.ip_address or "",
            "category": asset.category.name if asset.category else "",
            "color": asset.category.color if asset.category else "#4f8cff",
            "icon": asset.category.icon if asset.category and asset.category.icon else "📦",
            "status": asset_status(asset),
            "photo": url_for("uploaded_file", filename=asset.photos[0].filename) if asset.photos else None,
            "children": [_build_tree(c) for c in children],
        }

    all_roots = Asset.query.filter(Asset.parent_asset_id.is_(None)).order_by(Asset.name.asc()).all()

    # Prefer the UDMP root; fall back to root with most children
    udmp = None
    for r in all_roots:
        if "udmp" in (r.name or "").lower():
            udmp = r
            break
    if not udmp:
        udmp = max(all_roots, key=lambda r: len(r.children), default=None)

    tree_json = json.dumps(_build_tree(udmp)) if udmp else "null"
    return render_template("connection_map.html", tree_json=tree_json)


@app.route("/categories", methods=["GET", "POST"])
def category_list():
    form = CategoryForm()
    if form.validate_on_submit():
        name = (form.name.data or "").strip()
        if not name:
            flash("Category name is required.", "danger")
            return redirect(url_for("category_list"))

        if Category.query.filter(func.lower(Category.name) == name.lower()).first():
            flash("A category with that name already exists.", "danger")
            return redirect(url_for("category_list"))

        svg_text = (request.form.get("icon_svg") or "").strip()
        uploaded_svg = extract_svg_from_upload(request.files.get("icon_upload"))
        sanitised_svg = uploaded_svg or sanitise_svg_markup(svg_text)

        category = Category(
            name=name,
            description=(form.description.data or "").strip() or None,
            icon=(form.icon.data or "📦").strip()[:16] or "📦",
            icon_svg=sanitised_svg,
            color=(form.color.data or "#4f8cff").strip() or "#4f8cff",
        )
        db.session.add(category)
        db.session.commit()
        flash("Category created.", "success")
        return redirect(url_for("category_list"))

    counts = dict(
        db.session.query(Asset.category_id, func.count(Asset.id))
        .group_by(Asset.category_id)
        .all()
    )
    rows = [
        {"category": category, "asset_count": counts.get(category.id, 0)}
        for category in Category.query.order_by(Category.name.asc()).all()
    ]
    return render_template("categories.html", categories=rows, form=form)


@app.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
def category_edit(category_id):
    category = Category.query.get_or_404(category_id)
    form = CategoryForm(obj=category)

    if request.method == "GET":
        form.icon_svg.data = category.icon_svg or ""

    if form.validate_on_submit():
        name = (form.name.data or "").strip()
        existing = Category.query.filter(
            func.lower(Category.name) == name.lower(),
            Category.id != category.id,
        ).first()
        if existing:
            flash("Another category already uses that name.", "danger")
            return render_template("category_form.html", form=form, title="Edit category", category=category)

        svg_text = (request.form.get("icon_svg") or "").strip()
        uploaded_svg = extract_svg_from_upload(request.files.get("icon_upload"))
        sanitised_svg = uploaded_svg or sanitise_svg_markup(svg_text)

        category.name = name
        category.description = (form.description.data or "").strip() or None
        category.icon = (form.icon.data or "📦").strip()[:16] or "📦"
        category.icon_svg = sanitised_svg
        category.color = (form.color.data or "#4f8cff").strip() or "#4f8cff"
        db.session.commit()
        flash("Category updated.", "success")
        return redirect(url_for("category_list"))

    return render_template("category_form.html", form=form, title="Edit category", category=category)


@app.route("/categories/<int:category_id>/delete", methods=["POST"])
def category_delete(category_id):
    category = Category.query.get_or_404(category_id)
    if category.assets:
        flash("This category is in use and cannot be deleted yet.", "danger")
        return redirect(url_for("category_list"))

    db.session.delete(category)
    db.session.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("category_list"))


@app.route("/assets/new", methods=["GET", "POST"])
def asset_new():
    form = AssetForm()
    populate_asset_choices(form)
    fields = custom_field_definitions()

    if request.method == "GET":
        category_hint = request.args.get("category_id", type=int)
        if category_hint:
            form.category_id.data = category_hint

        if form.ping_interval_minutes.data in (None, ""):
            form.ping_interval_minutes.data = "5"

    selected_category = None
    selected_category_id = form.category_id.data or request.args.get("category_id", type=int)
    if selected_category_id:
        selected_category_obj = Category.query.get(selected_category_id)
        if selected_category_obj:
            selected_category = selected_category_obj.name

    form_category_groups = build_form_custom_field_groups(
        selected_category,
        fields,
        {},
    )

    if form.validate_on_submit():
        ip_address = (form.ip_address.data or "").strip() or None
        ping_enabled = bool(form.ping_enabled.data)

        asset = Asset(
            name=(form.name.data or "").strip(),
            category_id=form.category_id.data or None,
            subcategory=request.form.get("subcategory") or None,
            parent_asset_id=form.parent_asset_id.data or None,
            brand=(form.brand.data or "").strip() or None,
            model=(form.model.data or "").strip() or None,
            hostname=(form.hostname.data or "").strip() or None,
            ip_address=ip_address,
            domain_url=(form.domain_url.data or "").strip() or None,
            serial_number=(form.serial_number.data or "").strip() or None,
            location=(form.location.data or "").strip() or None,
            ping_enabled=ping_enabled,
            ping_interval_minutes=safe_ping_interval(form.ping_interval_minutes.data),
            last_ping_status="checking" if ping_enabled and ip_address else None,
            last_ping_checked_at=None,
            date_purchased=form.date_purchased.data,
            date_installed=form.date_installed.data,
            date_repaired=form.date_repaired.data,
            date_fixed=form.date_fixed.data,
            retire_date=form.retire_date.data,
            requires_attention=bool(form.requires_attention.data),
            requires_update=bool(form.requires_update.data),
            use_case=(form.use_case.data or "").strip() or None,
            related_urls=(form.related_urls.data or "").strip() or None,
            notes=(form.notes.data or "").strip() or None,
        )
        db.session.add(asset)
        db.session.flush()

        save_uploaded_photos(asset, request.files.getlist("photos"))
        save_custom_field_values(asset, request.form)
        db.session.commit()

        flash("Asset created.", "success")
        return redirect(url_for("asset_detail", asset_key=asset.asset_key))

    return render_template(
        "asset_form.html",
        form=form,
        title="Add asset",
        asset=None,
        brand_values=distinct_asset_values(Asset.brand),
        location_values=distinct_asset_values(Asset.location),
        custom_fields=fields,
        custom_values={},
        category_custom_groups=form_category_groups,
        subcategory="",
    )


@app.route("/a/<asset_key>")
def asset_detail(asset_key):
    asset = Asset.query.filter_by(asset_key=asset_key).first_or_404()

    all_field_definitions = custom_field_definitions()
    asset_field_values = custom_field_values_for_asset(asset)
    grouped_fields = build_asset_custom_field_groups(
        asset,
        all_field_definitions,
        asset_field_values,
    )

    universal_groups = [group for group in grouped_fields if group["key"] in {"core", "network", "timeline"}]
    _all_category_groups = [group for group in grouped_fields if group["key"] not in {"core", "network", "timeline"}]

    _hidden = set(json.loads(asset.hidden_groups)) if asset.hidden_groups else set()
    category_groups = [
        g for g in _all_category_groups
        if (g.get("scope", "") + "__" + g["key"]) not in _hidden
    ]

    change_logs = (
        AssetChangeLog.query
        .filter_by(asset_id=asset.id)
        .order_by(AssetChangeLog.changed_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "asset_detail.html",
        asset=asset,
        trail=get_asset_trail(asset),
        public_url=asset_public_url(asset),
        open_url=asset_open_url(asset),
        custom_field_pairs=custom_field_pairs(asset),
        universal_groups=universal_groups,
        category_groups=category_groups,
        change_logs=change_logs,
    )


@app.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
def asset_edit(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    form = AssetForm(obj=asset)
    populate_asset_choices(form, current_asset=asset)
    fields = custom_field_definitions()

    if request.method == "GET":
        form.category_id.data = asset.category_id or 0
        form.parent_asset_id.data = asset.parent_asset_id or 0
        form.requires_attention.data = asset.requires_attention
        form.requires_update.data = asset.requires_update
        form.ping_enabled.data = bool(asset.ping_enabled)
        form.ping_interval_minutes.data = str(asset.ping_interval_minutes or 5)
        form_subcategory = asset.subcategory or ""

    selected_category_name = None
    if form.category_id.data:
        selected_category_obj = Category.query.get(form.category_id.data)
        if selected_category_obj:
            selected_category_name = selected_category_obj.name
    elif asset.category:
        selected_category_name = asset.category.name

    form_category_groups = build_form_custom_field_groups(
        selected_category_name,
        fields,
        custom_field_values_for_asset(asset),
    )

    if form.validate_on_submit():
        selected_parent_id = form.parent_asset_id.data or None
        selected_parent = Asset.query.get(selected_parent_id) if selected_parent_id else None
        if selected_parent and is_descendant(selected_parent, asset):
            flash("Invalid hierarchy: an item cannot be its own ancestor or child.", "danger")
            return render_template(
                "asset_form.html",
                form=form,
                title="Edit asset",
                asset=asset,
                brand_values=distinct_asset_values(Asset.brand),
                location_values=distinct_asset_values(Asset.location),
                custom_fields=fields,
                custom_values=custom_field_values_for_asset(asset),
                category_custom_groups=form_category_groups,
                subcategory=asset.subcategory or "",
                hidden_group_keys=set(json.loads(asset.hidden_groups)) if asset.hidden_groups else set(),
            )

        old_ping_enabled = asset.ping_enabled
        old_ip_address = asset.ip_address
        old_snap = _asset_snapshot(asset)

        asset.name = (form.name.data or "").strip()
        asset.category_id = form.category_id.data or None
        asset.parent_asset_id = selected_parent_id
        asset.brand = (form.brand.data or "").strip() or None
        asset.model = (form.model.data or "").strip() or None
        asset.hostname = (form.hostname.data or "").strip() or None
        asset.ip_address = (form.ip_address.data or "").strip() or None
        asset.domain_url = (form.domain_url.data or "").strip() or None
        asset.serial_number = (form.serial_number.data or "").strip() or None
        asset.location = (form.location.data or "").strip() or None
        asset.ping_enabled = bool(form.ping_enabled.data)
        asset.ping_interval_minutes = safe_ping_interval(form.ping_interval_minutes.data)
        asset.date_purchased = form.date_purchased.data
        asset.date_installed = form.date_installed.data
        asset.date_repaired = form.date_repaired.data
        asset.date_fixed = form.date_fixed.data
        asset.retire_date = form.retire_date.data
        asset.requires_attention = bool(form.requires_attention.data)
        asset.requires_update = bool(form.requires_update.data)
        asset.subcategory = request.form.get("subcategory") or None
        _hidden_groups = request.form.getlist("hide_group")
        asset.hidden_groups = json.dumps(_hidden_groups) if _hidden_groups else None
        asset.use_case = (form.use_case.data or "").strip() or None
        asset.related_urls = (form.related_urls.data or "").strip() or None
        asset.notes = (form.notes.data or "").strip() or None

        if asset.ping_enabled and asset.ip_address:
            if (old_ip_address or "") != (asset.ip_address or "") or not old_ping_enabled:
                asset.last_ping_status = "checking"
                asset.last_ping_checked_at = None
        else:
            asset.last_ping_status = None
            asset.last_ping_checked_at = None

        new_cat = db.session.get(Category, asset.category_id) if asset.category_id else None
        new_parent = db.session.get(Asset, asset.parent_asset_id) if asset.parent_asset_id else None
        new_snap = {
            "Name": asset.name or "",
            "Category": new_cat.name if new_cat else "",
            "Brand": asset.brand or "",
            "Model": asset.model or "",
            "Serial number": asset.serial_number or "",
            "Location": asset.location or "",
            "Hostname": asset.hostname or "",
            "IP address": asset.ip_address or "",
            "Domain URL": asset.domain_url or "",
            "Ping monitoring": "Enabled" if asset.ping_enabled else "Disabled",
            "Requires attention": "Yes" if asset.requires_attention else "No",
            "Requires update": "Yes" if asset.requires_update else "No",
            "Retire date": str(asset.retire_date) if asset.retire_date else "",
            "Parent asset": new_parent.name if new_parent else "",
        }
        _record_asset_changes(asset, old_snap, new_snap)

        save_uploaded_photos(asset, request.files.getlist("photos"))
        save_custom_field_values(asset, request.form)
        db.session.commit()

        flash("Asset updated.", "success")
        return redirect(url_for("asset_detail", asset_key=asset.asset_key))

    return render_template(
        "asset_form.html",
        form=form,
        title="Edit asset",
        asset=asset,
        brand_values=distinct_asset_values(Asset.brand),
        location_values=distinct_asset_values(Asset.location),
        custom_fields=fields,
        custom_values=custom_field_values_for_asset(asset),
        category_custom_groups=form_category_groups,
        subcategory=asset.subcategory or "",
        hidden_group_keys=set(json.loads(asset.hidden_groups)) if asset.hidden_groups else set(),
    )


@app.route("/assets/<int:asset_id>/delete", methods=["POST"])
def asset_delete(asset_id):
    asset = Asset.query.get_or_404(asset_id)

    for child in asset.children:
        child.parent_asset_id = None

    for photo in asset.photos:
        try:
            (UPLOAD_DIR / photo.filename).unlink(missing_ok=True)
        except Exception:
            pass

    db.session.delete(asset)
    db.session.commit()
    flash("Asset deleted.", "success")
    return redirect(url_for("index"))


@app.route("/photos/<int:photo_id>/delete", methods=["POST"])
def photo_delete(photo_id):
    photo = AssetPhoto.query.get_or_404(photo_id)
    asset_key = photo.asset.asset_key

    try:
        (UPLOAD_DIR / photo.filename).unlink(missing_ok=True)
    except Exception:
        pass

    db.session.delete(photo)
    db.session.commit()
    flash("Photo deleted.", "success")
    return redirect(url_for("asset_detail", asset_key=asset_key))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(str(UPLOAD_DIR), filename)


@app.get("/api/ping-history/<int:asset_id>")
def api_ping_history(asset_id):
    records = (
        PingHistory.query
        .filter_by(asset_id=asset_id)
        .order_by(PingHistory.checked_at.desc())
        .limit(60)
        .all()
    )
    return jsonify([
        {"status": r.status, "t": r.checked_at.strftime("%Y-%m-%dT%H:%M:%SZ")}
        for r in records
    ])


@app.get("/api/ping-status")
def api_ping_status():
    assets = Asset.query.filter(
        Asset.ping_enabled.is_(True),
        Asset.ip_address.isnot(None),
        Asset.ip_address != "",
    ).all()
    return jsonify([
        {"id": a.id, "name": a.name, "ip": a.ip_address, "status": a.last_ping_status or "unknown"}
        for a in assets
    ])


@app.get("/api/image-search")
def api_image_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"error": "Missing query"}), 400

    searxng_url = get_setting("searxng_url")
    if not searxng_url:
        return jsonify({"error": "Image search is not configured. Add your SearXNG URL in Settings."}), 503

    search_url = searxng_url.rstrip("/") + "/search"
    try:
        resp = requests.get(
            search_url,
            params={
                "q": query,
                "categories": "images",
                "format": "json",
                "language": "auto",
                "safesearch": 1,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
    except requests.RequestException as exc:
        return jsonify({"error": f"Search request failed: {exc}"}), 502

    if resp.status_code != 200:
        return jsonify({"error": f"SearXNG error: HTTP {resp.status_code}"}), 502

    items = resp.json().get("results") or []
    results = [
        {
            "url": item.get("img_src") or item.get("url"),
            "thumbnail": item.get("thumbnail_src") or item.get("img_src") or item.get("url"),
            "title": item.get("title") or "",
            "width": item.get("img_width"),
            "height": item.get("img_height"),
        }
        for item in items
        if item.get("img_src") or item.get("url")
    ]
    return jsonify({"results": results})


@app.post("/api/image-search/download")
def api_image_search_download():
    asset_id = request.form.get("asset_id", type=int)
    image_url = (request.form.get("url") or "").strip()
    if not asset_id or not image_url:
        return jsonify({"error": "Missing asset_id or url"}), 400

    asset = Asset.query.get(asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404

    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return jsonify({"error": "Invalid image URL"}), 400

    try:
        resp = requests.get(image_url, timeout=20, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SWOps/1.0)"
        })
    except requests.RequestException as exc:
        return jsonify({"error": f"Download failed: {exc}"}), 502

    if resp.status_code != 200:
        return jsonify({"error": f"Download failed: HTTP {resp.status_code}"}), 502

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if not content_type.startswith("image/"):
        return jsonify({"error": "URL did not return an image"}), 400

    max_bytes = 12 * 1024 * 1024
    raw = io.BytesIO()
    for chunk in resp.iter_content(chunk_size=64 * 1024):
        raw.write(chunk)
        if raw.tell() > max_bytes:
            return jsonify({"error": "Image too large (max 12MB)"}), 413
    raw.seek(0)

    try:
        image = Image.open(raw)
        image.load()
    except Exception:
        return jsonify({"error": "Could not decode image"}), 400

    image = ImageOps.exif_transpose(image)
    image.thumbnail((1800, 1800))

    has_alpha = (
        "A" in image.getbands()
        or image.mode in {"RGBA", "LA", "PA"}
        or "transparency" in image.info
    )

    stem = secure_filename(f"{asset.brand or ''}_{asset.model or ''}".strip("_")) or "image"
    stem = stem[:80] or "image"

    if has_alpha:
        unique_name = f"{uuid.uuid4().hex}_{stem}.png"
        filepath = UPLOAD_DIR / unique_name
        image = image.convert("RGBA")
        image.save(filepath, format="PNG", optimize=True)
    else:
        unique_name = f"{uuid.uuid4().hex}_{stem}.jpg"
        filepath = UPLOAD_DIR / unique_name
        image = image.convert("RGB")
        image.save(filepath, format="JPEG", quality=88, optimize=True)

    photo = AssetPhoto(asset=asset, filename=unique_name)
    db.session.add(photo)
    db.session.commit()

    return jsonify({
        "ok": True,
        "filename": unique_name,
        "url": url_for("uploaded_file", filename=unique_name),
        "photo_id": photo.id,
    })


@app.route("/a/<asset_key>/qr.png")
def asset_qr(asset_key):
    asset = Asset.query.filter_by(asset_key=asset_key).first_or_404()
    qr_target = asset_public_url(asset)

    try:
        buffer = io.BytesIO(render_mini_qr_png(qr_target))
    except MiniQrRenderError as exc:
        app.logger.exception("Mini QR render failed for %s: %s", asset.asset_key, exc)
        img = qrcode.make(qr_target)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")

    buffer.seek(0)
    safe_name = secure_filename(asset.name or asset.asset_key) or asset.asset_key

    response = send_file(
        buffer,
        mimetype="image/png",
        download_name=f"{safe_name}.png",
        as_attachment=bool(request.args.get("download")),
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/settings")
def settings_page():
    return render_template(
        "settings.html",
        qr_base_url=get_setting("qr_base_url") or os.environ.get("APP_BASE_URL", ""),
        env_base_url=os.environ.get("APP_BASE_URL", ""),
        brand_values=distinct_asset_values(Asset.brand),
        location_values=distinct_asset_values(Asset.location),
        custom_fields=custom_field_definitions(),
        layout_mode=get_setting("layout_mode", "compact") or "compact",
        all_categories=Category.query.order_by(Category.name.asc()).all(),
        searxng_url=get_setting("searxng_url") or "",
    )


@app.route("/settings/image-search", methods=["POST"])
def settings_update_image_search():
    searxng_url = (request.form.get("searxng_url") or "").strip()
    set_setting("searxng_url", searxng_url or None)
    db.session.commit()
    flash("Image search settings saved.", "success")
    return redirect(url_for("settings_page"))


@app.route("/settings/qr-base-url", methods=["POST"])
def settings_update_qr_base_url():
    value = (request.form.get("qr_base_url") or "").strip()
    if value and not normalise_url(value):
        flash("Please enter a valid base URL, for example http://192.168.1.100:8085", "danger")
        return redirect(url_for("settings_page"))

    set_setting("qr_base_url", value or None)
    db.session.commit()
    flash("QR code base URL saved.", "success")
    return redirect(url_for("settings_page"))


@app.route("/settings/layout-mode", methods=["POST"])
def settings_update_layout_mode():
    value = (request.form.get("layout_mode") or "compact").strip()
    if value not in {"comfortable", "compact"}:
        flash("Unsupported layout mode.", "danger")
        return redirect(url_for("settings_page"))

    set_setting("layout_mode", value)
    db.session.commit()
    flash("Layout mode saved.", "success")
    return redirect(url_for("settings_page"))


@app.route("/settings/custom-fields/add", methods=["POST"])
def settings_custom_fields_add():
    label = (request.form.get("label") or "").strip()
    field_type = (request.form.get("field_type") or "text").strip()
    placeholder = (request.form.get("placeholder") or "").strip() or None

    if not label:
        flash("Custom field label is required.", "danger")
        return redirect(url_for("settings_page"))

    if field_type not in {"text", "textarea", "url", "date", "checkbox"}:
        flash("Unsupported custom field type.", "danger")
        return redirect(url_for("settings_page"))

    name = slugify(request.form.get("name") or label)
    if CustomFieldDefinition.query.filter_by(name=name).first():
        name = f"{name}_{uuid.uuid4().hex[:4]}"

    next_order = (db.session.query(func.max(CustomFieldDefinition.sort_order)).scalar() or 0) + 10
    db.session.add(
        CustomFieldDefinition(
            name=name,
            label=label,
            field_type=field_type,
            placeholder=placeholder,
            sort_order=next_order,
        )
    )
    db.session.commit()

    flash("Custom field added.", "success")
    return redirect(url_for("settings_page"))


@app.route("/settings/custom-fields/<int:field_id>/delete", methods=["POST"])
def settings_custom_fields_delete(field_id):
    field = CustomFieldDefinition.query.get_or_404(field_id)
    db.session.delete(field)
    db.session.commit()
    flash("Custom field deleted.", "success")
    return redirect(url_for("settings_page"))


@app.route("/settings/backup")
def settings_backup():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return send_file(
        make_backup_bytes(),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"swops_backup_{timestamp}.zip",
    )


@app.route("/settings/restore", methods=["POST"])
def settings_restore():
    backup_file = request.files.get("backup_file")
    if not backup_file or not backup_file.filename.lower().endswith(".zip"):
        flash("Please choose a valid backup ZIP file.", "danger")
        return redirect(url_for("settings_page"))

    temp_dir = parse_backup_zip(backup_file)
    try:
        db_file = temp_dir / "inventory.db"
        upload_dir = temp_dir / "uploads"
        if not db_file.exists():
            flash("Backup ZIP does not contain inventory.db", "danger")
            return redirect(url_for("settings_page"))

        db.session.remove()
        db.engine.dispose()

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if DATABASE_PATH.exists():
            DATABASE_PATH.unlink()
        shutil.copy2(db_file, DATABASE_PATH)

        if UPLOAD_DIR.exists():
            shutil.rmtree(UPLOAD_DIR)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        if upload_dir.exists() and upload_dir.is_dir():
            for item in upload_dir.rglob("*"):
                target = UPLOAD_DIR / item.relative_to(upload_dir)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)

        ensure_schema()
        db.create_all()
        flash("Backup restored successfully.", "success")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return redirect(url_for("settings_page"))


@app.post("/settings/import-csv")
def settings_import_csv():
    csv_file = request.files.get("csv_file")
    category_id = request.form.get("category_id", type=int) or None

    if not csv_file or not csv_file.filename.lower().endswith(".csv"):
        flash("Please choose a valid .csv file.", "danger")
        return redirect(url_for("settings_page"))

    import csv as csv_mod

    stream = io.StringIO(csv_file.stream.read().decode("utf-8-sig"))
    reader = csv_mod.DictReader(stream)

    mac_field = CustomFieldDefinition.query.filter_by(name="mac_address").first()
    if not mac_field:
        max_order = db.session.query(db.func.max(CustomFieldDefinition.sort_order)).scalar() or 0
        mac_field = CustomFieldDefinition(
            label="MAC Address",
            name="mac_address",
            field_type="text",
            placeholder="00:00:00:00:00:00",
            sort_order=max_order + 1,
        )
        db.session.add(mac_field)
        db.session.flush()

    created = skipped = 0
    for row in reader:
        name = (row.get("Name") or "").strip()
        ip = (row.get("IP Address") or "").strip() or None
        hostname = (row.get("Hostname") or "").strip() or None
        mac = (row.get("MAC Address") or "").strip() or None

        if not name:
            skipped += 1
            continue

        if Asset.query.filter_by(name=name).first():
            skipped += 1
            continue

        asset = Asset(
            name=name,
            hostname=hostname,
            ip_address=ip,
            category_id=category_id,
        )
        db.session.add(asset)
        db.session.flush()

        if mac:
            db.session.add(CustomFieldValue(asset_id=asset.id, field_id=mac_field.id, value=mac))

        created += 1

    db.session.commit()
    flash(f"Import complete: {created} device{'s' if created != 1 else ''} created, {skipped} skipped.", "success")
    return redirect(url_for("settings_page"))


@app.post("/assets/bulk-update")
def assets_bulk_update():
    asset_ids = [int(v) for v in request.form.getlist("asset_ids") if v.isdigit()]
    action = request.form.get("action", "").strip()

    if not asset_ids:
        flash("No assets selected.", "warning")
        return redirect(url_for("index"))

    assets_to_update = Asset.query.filter(Asset.id.in_(asset_ids)).all()

    if action == "assign_category":
        category_id = request.form.get("category_id", type=int)
        for asset in assets_to_update:
            asset.category_id = category_id
        db.session.commit()
        cat = Category.query.get(category_id) if category_id else None
        label = cat.name if cat else "None"
        flash(f"{len(assets_to_update)} device(s) assigned to '{label}'.", "success")

    elif action == "enable_ping":
        for asset in assets_to_update:
            asset.ping_enabled = True
        db.session.commit()
        flash(f"Ping check enabled for {len(assets_to_update)} device(s).", "success")

    elif action == "disable_ping":
        for asset in assets_to_update:
            asset.ping_enabled = False
        db.session.commit()
        flash(f"Ping check disabled for {len(assets_to_update)} device(s).", "success")

    elif action == "delete":
        count = len(assets_to_update)
        for asset in assets_to_update:
            db.session.delete(asset)
        db.session.commit()
        flash(f"{count} device{'s' if count != 1 else ''} deleted.", "success")

    else:
        flash("Unknown bulk action.", "danger")

    return redirect(url_for("index"))


with app.app_context():
    db.create_all()
    ensure_schema()
    seed_defaults()
    seed_category_fields_if_missing(db.session, CustomFieldDefinition)

start_ping_worker()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8085, debug=True)

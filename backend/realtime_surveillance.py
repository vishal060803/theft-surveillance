# backend/realtime_surveillance.py

import csv
import os
import shutil
import zipfile
import cv2
import time
import sqlite3
import threading
import numpy as np
import psutil
import geocoder
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta
from ultralytics import YOLO
from pushbullet import Pushbullet
import mediapipe as mp

import config

# =========================
# CONFIG
# =========================
API_KEY = config.API_KEY
SAVE_DIR = str(config.EVIDENCE_DIR)
DB_PATH = str(config.DB_PATH)
CAM_INDEX = config.CAM_INDEX
CAMERA_SOURCES = config.CAMERA_SOURCES

PERSON_WEIGHTS = str(config.PERSON_WEIGHTS)
WEAPON_WEIGHTS = str(config.WEAPON_WEIGHTS)
CONF_PERSON = 0.4
CONF_WEAPON = 0.45

PRE_SECONDS = 10
POST_SECONDS = 10

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_SKIP = 0
DRAW_HANDS = True
ENABLE_VIOLENCE = True
VIOLENCE_THRESHOLD = 9000

os.makedirs(SAVE_DIR, exist_ok=True)

# =========================
# LIVE LOCATION
# =========================
def get_live_location():
    try:
        g = geocoder.ip("me")
        if g.ok and g.latlng:
            lat, lon = g.latlng
            config.LOCATION_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(config.LOCATION_PATH, "w") as f:
                json.dump({"lat": lat, "lon": lon, "ts": datetime.now().isoformat()}, f)
            return [lat, lon]
    except Exception:
        pass
    return None

# =========================
# DB
# =========================
def init_db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        event_type TEXT,
        note TEXT,
        clip_path TEXT,
        zone_name TEXT,
        risk_score REAL,
        event_class TEXT,
        metadata TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS zone_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        zone_name TEXT,
        event_type TEXT,
        note TEXT,
        risk_score REAL,
        event_class TEXT,
        metadata TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        event_type TEXT,
        event_class TEXT,
        zone_name TEXT,
        risk_score REAL,
        priority TEXT,
        status TEXT,
        responder TEXT,
        acknowledged_at TEXT,
        message TEXT,
        escalation_level INTEGER DEFAULT 0,
        channels TEXT DEFAULT ''
    )
    """)
    cur.execute("PRAGMA table_info(events)")
    columns = {row[1] for row in cur.fetchall()}
    for column_name in ["zone_name", "risk_score", "event_class", "metadata"]:
        if column_name not in columns:
            column_type = "REAL" if column_name == "risk_score" else "TEXT"
            cur.execute(f"ALTER TABLE events ADD COLUMN {column_name} {column_type}")
    conn.commit()
    return conn


def build_evidence_metadata(camera_id, event_type, confidence=0.0, zone_name=None, risk_score=0.0,
                           frames_before=0, frames_after=0, location=None, event_class=None,
                           clip_path=None, timestamp=None):
    metadata = {
        "timestamp": timestamp or datetime.now().isoformat(timespec="seconds"),
        "camera_id": camera_id,
        "event_type": event_type,
        "confidence": round(float(confidence), 3),
        "zone": zone_name,
        "risk_score": round(float(risk_score), 1),
        "frames_before": int(frames_before),
        "frames_after": int(frames_after),
        "event_class": event_class or "unknown",
        "location": location or get_live_location() or {"lat": None, "lon": None},
        "clip_path": clip_path,
    }
    return metadata


def save_evidence_metadata(clip_path, metadata):
    if not clip_path:
        return None
    meta_path = f"{clip_path}.json"
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    os.chmod(meta_path, 0o600)
    return meta_path


def list_evidence(base_dir=None):
    target_dir = base_dir or SAVE_DIR
    entries = []
    if not os.path.isdir(target_dir):
        return entries
    for filename in sorted(os.listdir(target_dir)):
        if filename.lower().endswith(".mp4"):
            clip_path = os.path.join(target_dir, filename)
            meta_path = clip_path + ".json"
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    meta = {}
            if not meta:
                meta = {
                    "timestamp": os.path.splitext(filename)[0],
                    "camera_id": "unknown",
                    "event_type": "unknown",
                    "zone": None,
                    "risk_score": 0.0,
                    "confidence": 0.0,
                    "event_class": "unknown",
                }
            entries.append({
                "clip_path": os.path.basename(clip_path),
                "metadata_path": os.path.basename(meta_path),
                "timestamp": meta.get("timestamp") or os.path.splitext(filename)[0],
                "camera_id": meta.get("camera_id", "unknown"),
                "event_type": meta.get("event_type", "unknown"),
                "zone": meta.get("zone"),
                "risk_score": meta.get("risk_score", 0.0),
                "confidence": meta.get("confidence", 0.0),
                "event_class": meta.get("event_class", "unknown"),
                "location": meta.get("location"),
            })
    return entries


def export_events_csv(events=None, output_path=None):
    rows = events or []
    if not output_path:
        output_path = os.path.join(SAVE_DIR, "incident_export.csv")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fieldnames = [
        "timestamp", "camera_id", "event_type", "event_class", "zone", "confidence",
        "risk_score", "frames_before", "frames_after", "location"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "timestamp": row.get("timestamp") or "",
                "camera_id": row.get("camera_id") or "",
                "event_type": row.get("event_type") or "",
                "event_class": row.get("event_class") or "",
                "zone": row.get("zone") or "",
                "confidence": row.get("confidence") or 0.0,
                "risk_score": row.get("risk_score") or 0.0,
                "frames_before": row.get("frames_before") or 0,
                "frames_after": row.get("frames_after") or 0,
                "location": json.dumps(row.get("location") or {}),
            })
    os.chmod(output_path, 0o600)
    return output_path


def resolve_camera_sources():
    sources = []
    if config.CAMERA_SOURCES:
        for part in config.CAMERA_SOURCES.split(","):
            value = part.strip()
            if value:
                sources.append(value)
    if config.CAM_INDEX not in (None, -1):
        index_value = str(config.CAM_INDEX)
        if index_value not in sources:
            sources.append(index_value)
    return sources or ["0"]


def get_system_health_snapshot():
    camera_status = {}
    for source in resolve_camera_sources():
        source_key = source
        try:
            capture = cv2.VideoCapture(int(source) if str(source).isdigit() else str(source))
            ok = capture.isOpened()
            capture.release()
        except Exception:
            ok = False
        camera_status[source_key] = {
            "status": "online" if ok else "offline",
            "source": source_key,
        }
    try:
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(config.EVIDENCE_DIR) if os.path.exists(str(config.EVIDENCE_DIR)) else ".")
    except Exception:
        cpu_usage = 0.0
        memory = None
        disk = None
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "cpu_usage": cpu_usage,
        "memory_usage": round(memory.percent, 2) if memory else 0.0,
        "disk_usage": round((disk.used / disk.total) * 100, 2) if disk else 0.0,
        "camera_health": camera_status,
        "retention_days": config.RETENTION_DAYS,
        "environment": config.ENVIRONMENT,
    }


def create_evidence_backup(source_dir=None, backup_dir=None):
    source_root = source_dir or str(config.EVIDENCE_DIR)
    backup_root = backup_dir or str(config.BACKUP_DIR)
    os.makedirs(backup_root, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = os.path.join(backup_root, f"evidence_backup_{timestamp}.zip")

    if os.path.isdir(source_root):
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_name in sorted(os.listdir(source_root)):
                full_path = os.path.join(source_root, file_name)
                if os.path.isfile(full_path):
                    archive.write(full_path, arcname=file_name)
    else:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.txt", "No evidence files found.")

    os.chmod(archive_path, 0o600)
    return archive_path


def apply_retention_policy(base_dir=None, conn=None, retention_days=None):
    target_dir = base_dir or str(config.EVIDENCE_DIR)
    days = int(retention_days if retention_days is not None else config.RETENTION_DAYS)
    cutoff = datetime.now() - timedelta(days=days)
    deleted_files = []

    if os.path.isdir(target_dir):
        for entry in sorted(os.listdir(target_dir)):
            file_path = os.path.join(target_dir, entry)
            if os.path.isfile(file_path):
                if os.path.getmtime(file_path) < cutoff.timestamp():
                    os.remove(file_path)
                    deleted_files.append(file_path)

    if conn is None:
        conn = init_db()

    deleted_events = 0
    try:
        rows = conn.execute("SELECT id, ts, clip_path FROM events").fetchall()
        for event_id, event_ts, clip_path in rows:
            try:
                event_time = datetime.fromisoformat(event_ts)
            except Exception:
                try:
                    event_time = datetime.strptime(event_ts, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
            if event_time < cutoff:
                if clip_path and os.path.exists(clip_path):
                    try:
                        os.remove(clip_path)
                    except OSError:
                        pass
                conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
                deleted_events += 1
        conn.commit()
    except sqlite3.OperationalError:
        deleted_events = 0

    return {
        "deleted_files": deleted_files,
        "deleted_events": deleted_events,
        "retention_days": days,
        "cutoff": cutoff.isoformat(timespec="seconds"),
    }


def build_incident_summary(conn=None):
    if conn is None:
        conn = init_db()
    cur = conn.cursor()
    try:
        rows = cur.execute("SELECT ts, event_type, zone_name, risk_score FROM events ORDER BY ts DESC").fetchall()
    except sqlite3.OperationalError:
        return {
            "total_events": 0,
            "by_event_type": {},
            "by_zone": {},
            "avg_risk": 0.0,
            "high_risk_events": 0,
            "most_common_event": None,
            "most_common_zone": None,
        }

    by_event_type = defaultdict(int)
    by_zone = defaultdict(int)
    risk_values = []
    for ts, event_type, zone_name, risk_score in rows:
        if event_type:
            by_event_type[event_type] += 1
        if zone_name:
            by_zone[zone_name] += 1
        try:
            risk_val = float(risk_score or 0.0)
        except (TypeError, ValueError):
            risk_val = 0.0
        risk_values.append(risk_val)

    most_common_event = None
    if by_event_type:
        most_common_event = max(by_event_type.items(), key=lambda item: item[1])[0]
    most_common_zone = None
    if by_zone:
        most_common_zone = max(by_zone.items(), key=lambda item: item[1])[0]

    avg_risk = round(sum(risk_values) / len(risk_values), 2) if risk_values else 0.0
    high_risk_events = sum(1 for value in risk_values if value >= 75.0)

    return {
        "total_events": len(rows),
        "by_event_type": dict(sorted(by_event_type.items())),
        "by_zone": dict(sorted(by_zone.items())),
        "avg_risk": avg_risk,
        "high_risk_events": high_risk_events,
        "most_common_event": most_common_event,
        "most_common_zone": most_common_zone,
    }


def get_report_window_data(conn=None, window="day"):
    if conn is None:
        conn = init_db()
    cur = conn.cursor()
    try:
        rows = cur.execute("SELECT ts, event_type, zone_name, risk_score FROM events ORDER BY ts ASC").fetchall()
    except sqlite3.OperationalError:
        return []

    buckets = defaultdict(list)
    for ts, event_type, zone_name, risk_score in rows:
        try:
            dt = datetime.fromisoformat(ts) if ts else datetime.now()
        except ValueError:
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.now()

        if window.lower() == "week":
            key = dt.strftime("%Y-W%W")
        elif window.lower() == "month":
            key = dt.strftime("%Y-%m")
        else:
            key = dt.strftime("%Y-%m-%d")

        buckets[key].append({
            "event_type": event_type,
            "zone_name": zone_name,
            "risk_score": float(risk_score or 0.0),
        })

    result = []
    for key in sorted(buckets):
        bucket_rows = buckets[key]
        total_events = len(bucket_rows)
        high_risk = sum(1 for row in bucket_rows if row["risk_score"] >= 75.0)
        avg_risk = round(sum(row["risk_score"] for row in bucket_rows) / total_events, 2) if total_events else 0.0
        event_counts = defaultdict(int)
        zone_counts = defaultdict(int)
        for row in bucket_rows:
            if row["event_type"]:
                event_counts[row["event_type"]] += 1
            if row["zone_name"]:
                zone_counts[row["zone_name"]] += 1
        result.append({
            "day": key,
            "total_events": total_events,
            "high_risk": high_risk,
            "avg_risk": avg_risk,
            "most_common_event": max(event_counts.items(), key=lambda item: item[1])[0] if event_counts else None,
            "top_zone": max(zone_counts.items(), key=lambda item: item[1])[0] if zone_counts else None,
        })
    return result


def export_report_csv(rows, output_path=None):
    if not output_path:
        output_path = os.path.join(SAVE_DIR, "report_export.csv")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fieldnames = ["day", "total_events", "high_risk", "avg_risk", "most_common_event", "top_zone"]
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "day": row.get("day") or "",
                "total_events": row.get("total_events") or 0,
                "high_risk": row.get("high_risk") or 0,
                "avg_risk": row.get("avg_risk") or 0.0,
                "most_common_event": row.get("most_common_event") or "",
                "top_zone": row.get("top_zone") or "",
            })
    os.chmod(output_path, 0o600)
    return output_path


def benchmark_detection_pipeline(true_positives=0, false_positives=0, false_negatives=0, model_versions=None):
    tp = float(true_positives or 0)
    fp = float(false_positives or 0)
    fn = float(false_negatives or 0)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    false_alarm_rate = fp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
        "false_alarm_rate": round(false_alarm_rate, 4),
        "model_versions": list(model_versions or ["yolov8s", "yolov10n"]),
    }


def evaluate_scene_conditions(lighting_score=0.0, crowd_density=0.0, video_quality=0.0):
    lighting_state = "good" if lighting_score >= 0.7 else "moderate" if lighting_score >= 0.4 else "poor"
    crowd_state = "manageable" if crowd_density <= 0.5 else "dense" if crowd_density <= 0.8 else "crowded"
    quality_state = "good" if video_quality >= 0.7 else "acceptable" if video_quality >= 0.5 else "low"
    readiness_score = (lighting_score + (1.0 - crowd_density) + video_quality) / 3.0
    readiness = "ready" if readiness_score >= 0.7 else "watch" if readiness_score >= 0.5 else "needs_attention"
    return {
        "lighting": {"score": round(float(lighting_score), 4), "state": lighting_state},
        "crowd": {"score": round(float(crowd_density), 4), "state": crowd_state},
        "quality": {"score": round(float(video_quality), 4), "state": quality_state},
        "overall_readiness": readiness,
        "readiness_score": round(readiness_score, 4),
    }


def measure_event_latency(detection_ms=0, alert_ms=0, review_ms=0):
    detection_latency_ms = float(detection_ms or 0)
    alert_delay_ms = float(alert_ms or 0)
    review_time_ms = float(review_ms or 0)
    return {
        "detection_latency_ms": round(detection_latency_ms, 2),
        "alert_delay_ms": round(alert_delay_ms, 2),
        "review_time_ms": round(review_time_ms, 2),
        "total_latency_ms": round(detection_latency_ms + alert_delay_ms + review_time_ms, 2),
    }


def run_validation_suite(true_positives=0, false_positives=0, false_negatives=0,
                        lighting_score=0.0, crowd_density=0.0, video_quality=0.0,
                        detection_ms=0, alert_ms=0, review_ms=0, model_versions=None):
    benchmark = benchmark_detection_pipeline(true_positives, false_positives, false_negatives, model_versions)
    scene_conditions = evaluate_scene_conditions(lighting_score, crowd_density, video_quality)
    latency = measure_event_latency(detection_ms, alert_ms, review_ms)
    pass_criteria = (
        benchmark["precision"] >= 0.7 and
        benchmark["false_alarm_rate"] <= 0.2 and
        scene_conditions["overall_readiness"] in {"ready", "watch"} and
        latency["total_latency_ms"] <= 2000
    )
    return {
        "overall_status": "pass" if pass_criteria else "needs_attention",
        "benchmark": benchmark,
        "scene_conditions": scene_conditions,
        "latency": latency,
        "summary": {
            "precision_target_met": benchmark["precision"] >= 0.7,
            "false_alarm_target_met": benchmark["false_alarm_rate"] <= 0.2,
            "scene_readiness": scene_conditions["overall_readiness"],
            "latency_target_met": latency["total_latency_ms"] <= 2000,
        },
    }


def log_event(conn, event_type, note, clip_path, zone_name=None, risk_score=0.0, event_class="unknown", metadata=None):
    if conn is None:
        return
    cur = conn.cursor()
    payload = metadata if metadata is not None else {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "camera_id": "unknown",
        "event_type": event_type,
        "confidence": 0.0,
        "zone": zone_name,
        "frames_before": 0,
        "frames_after": 0,
        "location": get_live_location() or {"lat": None, "lon": None},
        "risk_score": float(risk_score),
        "event_class": event_class,
    }
    payload_json = json.dumps(payload)
    try:
        cur.execute(
            "INSERT INTO events (ts, event_type, note, clip_path, zone_name, risk_score, event_class, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), event_type, note, clip_path, zone_name, float(risk_score), event_class, payload_json)
        )
    except sqlite3.OperationalError:
        try:
            cur.execute("ALTER TABLE events ADD COLUMN zone_name TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE events ADD COLUMN risk_score REAL")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE events ADD COLUMN event_class TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE events ADD COLUMN metadata TEXT")
        except sqlite3.OperationalError:
            pass
        cur.execute(
            "INSERT INTO events (ts, event_type, note, clip_path, zone_name, risk_score, event_class, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), event_type, note, clip_path, zone_name, float(risk_score), event_class, payload_json)
        )
    conn.commit()


def record_zone_event(conn, zone_name, event_type, note, risk_score=0.0, event_class="unknown", metadata=None):
    if conn is None or not zone_name:
        return
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS zone_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        zone_name TEXT,
        event_type TEXT,
        note TEXT,
        risk_score REAL,
        event_class TEXT,
        metadata TEXT
    )
    """)
    payload = metadata if metadata is not None else {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "camera_id": "unknown",
        "event_type": event_type,
        "confidence": 0.0,
        "zone": zone_name,
        "frames_before": 0,
        "frames_after": 0,
        "location": get_live_location() or {"lat": None, "lon": None},
        "risk_score": float(risk_score),
        "event_class": event_class,
    }
    cur.execute(
        "INSERT INTO zone_events (ts, zone_name, event_type, note, risk_score, event_class, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), zone_name, event_type, note, float(risk_score), event_class, json.dumps(payload))
    )
    conn.commit()

# =========================
# PHASE 7: ALERTS, NOTIFICATIONS, AND SECURITY WORKFLOW
# =========================
def get_alert_priority(event_class, risk_score=0.0):
    event_class = (event_class or "").lower()
    risk_score = float(risk_score or 0.0)
    if risk_score >= 90 or event_class in {"emergency_signal", "weapon_seen", "theft_attempt"}:
        return "critical"
    if risk_score >= 60 or event_class in {"entering_restricted_area", "loitering", "aggressive_behavior", "suspicious_movement"}:
        return "high"
    if risk_score >= 45:
        return "medium"
    return "low"


def build_alert_message(event_type, event_class=None, zone_name=None, risk_score=0.0, note=None):
    priority = get_alert_priority(event_class, risk_score)
    title = f"🚨 {event_type or 'SECURITY_ALERT'}"
    body = (
        f"body: {note or 'Security alert triggered'} | "
        f"Zone: {zone_name or 'overall'} | Risk: {float(risk_score or 0.0):.1f} | "
        f"Priority: {priority.upper()}"
    )
    return {
        "title": title,
        "body": body,
        "priority": priority,
        "zone_name": zone_name,
        "risk_score": float(risk_score or 0.0),
        "event_type": event_type,
        "event_class": event_class,
    }


def send_alert_notifications(pb, alert_message, channels=None):
    channels = channels or ["pushbullet", "email", "sms", "whatsapp"]
    title = alert_message.get("title", "Security Alert")
    body = alert_message.get("body", "")
    sent = {
        "pushbullet": False,
        "email": False,
        "sms": False,
        "whatsapp": False,
    }

    try:
        if "pushbullet" in channels and pb is not None:
            pb.push_note(title, body)
            sent["pushbullet"] = True
            latlng = get_live_location()
            if latlng:
                lat, lon = latlng
                pb.push_link("📍 Live Shop Location", f"https://www.google.com/maps?q={lat},{lon}")
    except Exception as exc:
        print(f"[PushBullet Error] {exc}")

    for channel in ["email", "sms", "whatsapp"]:
        if channel in channels:
            sent[channel] = True
            print(f"[{channel.upper()} Alert] {title} - {body}")

    return sent


def log_alert(conn, event_type, event_class, zone_name=None, risk_score=0.0, note=None, priority=None,
              channels=None, escalation_level=0):
    if conn is None:
        return None
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        event_type TEXT,
        event_class TEXT,
        zone_name TEXT,
        risk_score REAL,
        priority TEXT,
        status TEXT,
        responder TEXT,
        acknowledged_at TEXT,
        message TEXT,
        escalation_level INTEGER DEFAULT 0,
        channels TEXT DEFAULT ''
    )
    """)
    priority = priority or get_alert_priority(event_class, risk_score)
    ts = datetime.now().isoformat(timespec="seconds")
    message = note or f"{event_type or 'Security alert'} detected"

    columns = [row[1] for row in cur.execute("PRAGMA table_info(alerts)").fetchall()]
    if "escalation_level" in columns and "channels" in columns:
        cur.execute(
            "INSERT INTO alerts (ts, event_type, event_class, zone_name, risk_score, priority, status, responder, acknowledged_at, message, escalation_level, channels) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, event_type, event_class, zone_name, float(risk_score or 0.0), priority, "open", None, None, message, int(escalation_level), ",".join(channels or []))
        )
    else:
        cur.execute(
            "INSERT INTO alerts (ts, event_type, event_class, zone_name, risk_score, priority, status, responder, acknowledged_at, message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, event_type, event_class, zone_name, float(risk_score or 0.0), priority, "open", None, None, message)
        )
    conn.commit()
    alert_id = cur.lastrowid
    alert = {
        "id": alert_id,
        "ts": ts,
        "event_type": event_type,
        "event_class": event_class,
        "zone_name": zone_name,
        "risk_score": float(risk_score or 0.0),
        "priority": priority,
        "status": "open",
        "responder": None,
        "acknowledged_at": None,
        "message": message,
        "escalation_level": int(escalation_level),
        "channels": channels or ["pushbullet", "email", "sms", "whatsapp"],
    }
    return alert


def list_alerts(conn=None):
    if conn is None:
        conn = init_db()
    cur = conn.cursor()
    try:
        columns = [row[1] for row in cur.execute("PRAGMA table_info(alerts)").fetchall()]
    except sqlite3.OperationalError:
        return []
    if not columns:
        return []

    selected = [
        col for col in ["id", "ts", "event_type", "event_class", "zone_name", "risk_score", "priority", "status", "responder", "acknowledged_at", "message", "escalation_level", "channels"]
        if col in columns
    ]
    if not selected:
        return []

    query = f"SELECT {', '.join(selected)} FROM alerts ORDER BY id DESC"
    try:
        rows = cur.execute(query).fetchall()
    except sqlite3.OperationalError:
        return []
    alerts = []
    for row in rows:
        obj = dict(zip(selected, row))
        alert = {
            "id": obj.get("id"),
            "ts": obj.get("ts"),
            "event_type": obj.get("event_type"),
            "event_class": obj.get("event_class"),
            "zone_name": obj.get("zone_name"),
            "risk_score": float(obj.get("risk_score") or 0.0),
            "priority": obj.get("priority"),
            "status": obj.get("status"),
            "responder": obj.get("responder"),
            "acknowledged_at": obj.get("acknowledged_at"),
            "message": obj.get("message"),
            "escalation_level": int(obj.get("escalation_level") or 0),
            "channels": [c for c in str(obj.get("channels") or "").split(",") if c],
        }
        alerts.append(alert)
    return alerts


def acknowledge_alert(conn, alert_id, responder_name="security"):
    if conn is None:
        return {"acknowledged": False, "error": "No database connection was provided."}
    cur = conn.cursor()
    cur.execute("SELECT id, status, responder, acknowledged_at FROM alerts WHERE id = ?", (alert_id,))
    row = cur.fetchone()
    if row is None:
        return {"acknowledged": False, "error": "Alert not found", "id": alert_id}
    acknowledged_at = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "UPDATE alerts SET status = ?, responder = ?, acknowledged_at = ? WHERE id = ?",
        ("acknowledged", responder_name, acknowledged_at, alert_id)
    )
    conn.commit()
    return {
        "acknowledged": True,
        "id": alert_id,
        "responder": responder_name,
        "status": "acknowledged",
        "acknowledged_at": acknowledged_at,
    }


def push_notify(pb, title, body):
    try:
        pb.push_note(title, body)
        latlng = get_live_location()
        if latlng:
            lat, lon = latlng
            pb.push_link("📍 Live Shop Location", f"https://www.google.com/maps?q={lat},{lon}")
    except Exception as e:
        print(f"[PushBullet Error] {e}")

# =========================
# PHASE 5: EVENT CLASSIFICATION + RISK SCORING
# =========================
EVENT_DEDUPE_WINDOW_SEC = 20
LAST_ALERT_KEYS = {}


def classify_event(event_type, zone_name=None, suspicious_track_count=0, dwell_seconds=0.0, confidence=0.0,
                  movement=0.0, speed=0.0, violence_detected=False):
    if event_type is None:
        return "normal_activity", 0.0, "No event classification triggered."

    if event_type == "EMERGENCY_SIGNAL":
        event_class = "emergency_signal"
        risk_score = 99.0
        note = "High-risk emergency signal detected. Immediate attention required."
    elif event_type == "WEAPON_DETECTED":
        event_class = "weapon_seen"
        risk_score = 91.0
        note = "Weapon detected in the monitored area."
    elif event_type == "SUSPICIOUS_PERSON":
        restricted_bonus = 18 if zone_name == "restricted" else 0
        if zone_name == "restricted":
            event_class = "entering_restricted_area"
            base = 78
        elif dwell_seconds >= 18 or suspicious_track_count >= 2:
            event_class = "loitering"
            base = 72
        elif movement >= 70 or speed >= 120:
            event_class = "theft_attempt"
            base = 83
        elif violence_detected or speed >= 80:
            event_class = "aggressive_behavior"
            base = 76
        else:
            event_class = "suspicious_movement"
            base = 61
        risk_score = min(100.0, float(base + (confidence * 20.0) + (dwell_seconds * 0.7) + (suspicious_track_count * 8.0) + restricted_bonus))
        if event_class == "suspicious_movement":
            note = "Suspicious person movement detected in the monitored zone."
        elif event_class == "loitering":
            note = "Prolonged loitering suggests suspicious dwell time in the area."
        elif event_class == "theft_attempt":
            note = "Theft-like movement pattern detected with elevated risk."
        elif event_class == "aggressive_behavior":
            note = "Aggressive or hurried behavior suggests a higher security risk."
        elif event_class == "entering_restricted_area":
            note = "Restricted area activity detected with high risk."
        else:
            note = "Suspicious behavior detected with a moderate risk score."
    else:
        event_class = "normal_activity"
        risk_score = max(0.0, min(25.0, confidence * 20.0))
        note = "Normal activity observed."

    if event_class == "normal_activity":
        risk_score = min(25.0, risk_score)
    return event_class, round(risk_score, 1), f"Event class: {event_class}; risk={round(risk_score, 1)}; detail={note}"


def should_emit_event(event_class, zone_name=None):
    key = f"{event_class}:{zone_name or 'overall'}"
    now = time.time()
    last_seen = LAST_ALERT_KEYS.get(key, 0)
    if last_seen and (now - last_seen) < EVENT_DEDUPE_WINDOW_SEC:
        return False
    LAST_ALERT_KEYS[key] = now
    return True


TRACKER_NAME = "bytetrack.yaml"
TRACK_HISTORY = {}
ZONE_LAYOUT = config.ZONE_LAYOUT if hasattr(config, "ZONE_LAYOUT") else [
    {"name": "entrance", "x": 0.00, "y": 0.00, "w": 0.35, "h": 0.35},
    {"name": "cashier", "x": 0.35, "y": 0.00, "w": 0.30, "h": 0.35},
    {"name": "storage", "x": 0.00, "y": 0.38, "w": 0.42, "h": 0.35},
    {"name": "restricted", "x": 0.42, "y": 0.38, "w": 0.32, "h": 0.35},
    {"name": "exit", "x": 0.70, "y": 0.00, "w": 0.30, "h": 0.35},
]
ZONE_HISTORY = {
    zone["name"]: {
        "activity_count": 0,
        "suspicious_count": 0,
        "event_count": 0,
        "dwell_seconds": 0.0,
        "last_seen": time.time(),
    }
    for zone in ZONE_LAYOUT
}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def get_zone_for_point(x_norm, y_norm):
    for zone in ZONE_LAYOUT:
        x = float(zone.get("x", 0.0))
        y = float(zone.get("y", 0.0))
        w = float(zone.get("w", 0.0))
        h = float(zone.get("h", 0.0))
        if x_norm >= x and x_norm <= x + w and y_norm >= y and y_norm <= y + h:
            return zone["name"]
    return None


def get_zone_hotspots():
    hotspots = []
    for zone in ZONE_LAYOUT:
        zone_name = zone["name"]
        state = ZONE_HISTORY.setdefault(zone_name, {
            "activity_count": 0,
            "suspicious_count": 0,
            "event_count": 0,
            "dwell_seconds": 0.0,
            "last_seen": time.time(),
        })
        activity = max(int(state.get("activity_count", 0)), 0)
        suspicious = max(int(state.get("suspicious_count", 0)), 0)
        events = max(int(state.get("event_count", 0)), 0)
        dwell = float(state.get("dwell_seconds", 0.0))
        crowd_density = round(activity / max(1.0, dwell / 10.0), 2) if dwell > 0 else 0.0
        score = min(100, int((events * 30) + (suspicious * 25) + (activity * 2) + (dwell * 0.8) + (crowd_density * 5)))
        if score >= 80:
            risk_level = "critical"
        elif score >= 60:
            risk_level = "high"
        elif score >= 35:
            risk_level = "medium"
        else:
            risk_level = "low"
        hotspots.append({
            "name": zone_name,
            "x": float(zone.get("x", 0.0)),
            "y": float(zone.get("y", 0.0)),
            "w": float(zone.get("w", 0.0)),
            "h": float(zone.get("h", 0.0)),
            "activity_count": activity,
            "suspicious_count": suspicious,
            "event_count": events,
            "dwell_seconds": round(dwell, 1),
            "crowd_density": crowd_density,
            "hotspot_score": score,
            "risk_level": risk_level,
        })
    return sorted(hotspots, key=lambda item: item["hotspot_score"], reverse=True)


def update_zone_activity(frame, track_result=None, suspicious_ids=None, event_zone=None):
    if frame is None:
        return get_zone_hotspots()

    h, w = frame.shape[:2]
    suspicious_ids = set(suspicious_ids or [])

    if track_result and hasattr(track_result, "boxes") and track_result.boxes is not None:
        boxes = track_result.boxes
        if boxes.id is not None:
            cls_list = boxes.cls.int().tolist() if boxes.cls is not None else []
            id_list = boxes.id.int().tolist()
            xyxy = boxes.xyxy.cpu().tolist()
            for index, track_id in enumerate(id_list):
                if index >= len(cls_list):
                    continue
                if int(cls_list[index]) != 0:
                    continue
                x1, y1, x2, y2 = xyxy[index]
                cx = (x1 + x2) / 2.0 / max(w, 1)
                cy = (y1 + y2) / 2.0 / max(h, 1)
                zone_name = get_zone_for_point(cx, cy)
                if not zone_name:
                    continue
                state = ZONE_HISTORY.setdefault(zone_name, {
                    "activity_count": 0,
                    "suspicious_count": 0,
                    "event_count": 0,
                    "dwell_seconds": 0.0,
                    "last_seen": time.time(),
                })
                state["activity_count"] += 1
                state["dwell_seconds"] += 1.0
                state["last_seen"] = time.time()
                if track_id in suspicious_ids:
                    state["suspicious_count"] += 1

    if event_zone:
        state = ZONE_HISTORY.setdefault(event_zone, {
            "activity_count": 0,
            "suspicious_count": 0,
            "event_count": 0,
            "dwell_seconds": 0.0,
            "last_seen": time.time(),
        })
        state["event_count"] += 1
        state["suspicious_count"] += 1
        state["last_seen"] = time.time()

    return get_zone_hotspots()


person_model = YOLO(PERSON_WEIGHTS)
weapon_model = YOLO(WEAPON_WEIGHTS) if os.path.isfile(WEAPON_WEIGHTS) else None

mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

def is_open_palm(hand_landmarks, w, h):
    tips = [4, 8, 12, 16, 20]
    pips = [2, 6, 10, 14, 18]
    lm = hand_landmarks.landmark
    pts = [(int(lm[i].x * w), int(lm[i].y * h)) for i in range(21)]
    wrist = pts[0]
    def dist(a,b): return np.hypot(a[0]-b[0], a[1]-b[1])
    fingers_up = sum(dist(pts[tip], wrist) > dist(pts[pip], wrist) for tip,pip in zip(tips,pips))
    return fingers_up >= 5

_prev_gray = None
def violence_score(frame):
    global _prev_gray
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (11,11), 0)
    score = 0
    if _prev_gray is not None:
        diff = cv2.absdiff(gray, _prev_gray)
        score = int(cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1].sum() / 255)
    _prev_gray = gray
    return score

def save_clip(pre_frames, post_frames, out_path, fps):
    frames = (pre_frames or []) + (post_frames or [])
    if not frames: return
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    os.chmod(os.path.dirname(out_path), 0o700)
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    if fps <= 0 or np.isnan(fps): fps=20
    vw = cv2.VideoWriter(out_path, fourcc, fps, (w,h))
    for f in frames: vw.write(f)
    vw.release()
    os.chmod(out_path, 0o600)
    print(f"🎥 Saved clip: {out_path} ({len(frames)} frames)")


def update_track_history(track_result, frame_time):
    global TRACK_HISTORY
    if not track_result or not hasattr(track_result, "boxes") or track_result.boxes is None:
        return []

    boxes = track_result.boxes
    if boxes.id is None:
        return []

    tracked_ids = []
    cls_list = boxes.cls.int().tolist() if boxes.cls is not None else []
    id_list = boxes.id.int().tolist()
    xyxy = boxes.xyxy.cpu().tolist()

    for index, track_id in enumerate(id_list):
        if index >= len(cls_list):
            continue
        if int(cls_list[index]) != 0:
            continue

        x1, y1, x2, y2 = xyxy[index]
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        current = TRACK_HISTORY.setdefault(track_id, {
            "first_seen": frame_time,
            "last_seen": frame_time,
            "cx": cx,
            "cy": cy,
            "speed": 0.0,
            "total_distance": 0.0,
            "history": [(cx, cy)],
        })

        prev_x = current["cx"]
        prev_y = current["cy"]
        distance = np.hypot(cx - prev_x, cy - prev_y)
        current["total_distance"] += distance
        current["speed"] = distance / max(frame_time - current["last_seen"], 0.1)
        current["last_seen"] = frame_time
        current["cx"] = cx
        current["cy"] = cy
        current["history"].append((cx, cy))
        if len(current["history"]) > 20:
            current["history"] = current["history"][-20:]

        tracked_ids.append(track_id)

    suspicious_ids = []
    for track_id in tracked_ids:
        state = TRACK_HISTORY.get(track_id)
        if not state:
            continue
        elapsed = frame_time - state["first_seen"]
        movement = state["total_distance"]
        speed = state["speed"]
        if elapsed >= 8 and movement < 25 and speed < 5:
            suspicious_ids.append(track_id)
        elif speed > 150:
            suspicious_ids.append(track_id)
    return suspicious_ids

# =========================
# CAMERA SOURCE CONFIGURATION
# =========================
def resolve_camera_sources():
    if CAMERA_SOURCES:
        sources = [item.strip() for item in CAMERA_SOURCES.split(",") if item.strip()]
        return sources
    return [CAM_INDEX]


def open_camera(source, retries=3, delay=2.0):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            cap = cv2.VideoCapture(source)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                return cap
            last_error = f"camera source {source} failed to open (attempt {attempt}/{retries})"
        except Exception as exc:
            last_error = f"camera source {source} raised {exc} (attempt {attempt}/{retries})"
        time.sleep(delay)
    print(f"[Camera] {last_error}")
    return None


def is_valid_frame(frame):
    return frame is not None and hasattr(frame, "shape") and len(frame.shape) >= 2 and frame.shape[0] > 0 and frame.shape[1] > 0


def process_stream(source, conn, pb, stream_label):
    cap = open_camera(source, retries=3, delay=2.0)
    if cap is None:
        print(f"[Camera] {stream_label} unavailable; retrying later.")
        conn.close()
        return

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 20
        ring = deque(maxlen=int(PRE_SECONDS * fps))
        post_buf_len = int(POST_SECONDS * fps)
        capturing_post = False
        post_counter = 0
        pending = None
        last_event_ts = 0
        event_cooldown_sec = 6

        print(f"✅ Real-time monitoring started for {stream_label} ({source}).")
        while True:
            try:
                ret, frame = cap.read()
                if not ret or not is_valid_frame(frame):
                    print(f"[Camera] Lost frame from {stream_label}. Reconnecting...")
                    cap.release()
                    cap = open_camera(source, retries=3, delay=2.0)
                    if cap is None:
                        time.sleep(3)
                        continue
                    continue

                h, w = frame.shape[:2]
                ring.append(frame.copy())

                now = time.time()
                person_res = person_model.track(
                    frame,
                    imgsz=480,
                    conf=CONF_PERSON,
                    persist=True,
                    tracker=TRACKER_NAME,
                    verbose=False,
                )
                annotated = person_res[0].plot() if person_res else frame.copy()
                suspicious_tracks = update_track_history(person_res[0], now) if person_res else []
                zone_scores = get_zone_hotspots()
                event_zone = None
                if person_res and person_res[0].boxes and person_res[0].boxes.id is not None:
                    zone_counts = defaultdict(int)
                    cls_list = person_res[0].boxes.cls.int().tolist() if person_res[0].boxes.cls is not None else []
                    xyxy = person_res[0].boxes.xyxy.cpu().tolist()
                    for index, box in enumerate(xyxy):
                        if index >= len(cls_list):
                            continue
                        if int(cls_list[index]) != 0:
                            continue
                        x1, y1, x2, y2 = box
                        cx = (x1 + x2) / 2.0 / max(w, 1)
                        cy = (y1 + y2) / 2.0 / max(h, 1)
                        zone_name = get_zone_for_point(cx, cy)
                        if zone_name:
                            zone_counts[zone_name] += 1
                    if zone_counts:
                        event_zone = max(zone_counts, key=zone_counts.get)

                update_zone_activity(frame, person_res[0] if person_res else None, suspicious_tracks, event_zone)
                zone_scores = get_zone_hotspots()

                weapon_detected = False
                if weapon_model:
                    wres = weapon_model.predict(frame, imgsz=640, conf=CONF_WEAPON, verbose=False)
                    if wres and wres[0].boxes and len(wres[0].boxes) > 0:
                        weapon_detected = True
                        annotated = wres[0].plot()

                vscore = violence_score(frame) if ENABLE_VIOLENCE else 0
                violence_detected = ENABLE_VIOLENCE and (vscore > VIOLENCE_THRESHOLD)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hand_out = hands.process(rgb)
                emergency = False
                if hand_out.multi_hand_landmarks:
                    for hlm in hand_out.multi_hand_landmarks:
                        if is_open_palm(hlm, w, h):
                            emergency = True
                            if DRAW_HANDS:
                                mp_draw.draw_landmarks(annotated, hlm, mp_hands.HAND_CONNECTIONS)
                            break

                event_type, note = None, None
                if emergency:
                    event_type, note = "EMERGENCY_SIGNAL", "Owner raised 5-finger emergency sign"
                elif weapon_detected:
                    event_type, note = "WEAPON_DETECTED", "Restricted weapon detected"
                elif suspicious_tracks:
                    event_type, note = "SUSPICIOUS_PERSON", f"Tracked person activity suggests loitering or unusual movement ({len(suspicious_tracks)} tracked person(s))"

                if event_type and (now - last_event_ts) > event_cooldown_sec:
                    event_class, risk_score, classified_note = classify_event(
                        event_type,
                        zone_name=event_zone,
                        suspicious_track_count=len(suspicious_tracks),
                        dwell_seconds=sum(1 for _ in range(len(suspicious_tracks))) * 2,
                        confidence=CONF_PERSON,
                        movement=0.0,
                        speed=float(max((state.get("speed", 0.0) for state in [TRACK_HISTORY.get(track_id, {}) for track_id in suspicious_tracks]), default=0.0)),
                        violence_detected=violence_detected,
                    )

                    if not should_emit_event(event_class, event_zone):
                        continue

                    last_event_ts = now
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clip_path = os.path.join(SAVE_DIR, f"{event_type}_{timestamp}.mp4")
                    hotspot_score = 0
                    if event_zone:
                        zone_summary = next((item for item in zone_scores if item["name"] == event_zone), None)
                        if zone_summary:
                            hotspot_score = zone_summary["hotspot_score"]
                    risk_score = max(float(risk_score), float(hotspot_score))
                    final_note = classified_note if event_class != "normal_activity" else note
                    metadata = build_evidence_metadata(
                        camera_id=stream_label,
                        event_type=event_type,
                        confidence=CONF_PERSON,
                        zone_name=event_zone,
                        risk_score=risk_score,
                        frames_before=len(ring),
                        frames_after=post_buf_len,
                        location=get_live_location() or {"lat": None, "lon": None},
                        event_class=event_class,
                        clip_path=clip_path,
                        timestamp=datetime.now().isoformat(timespec="seconds"),
                    )
                    save_evidence_metadata(clip_path, metadata)
                    log_event(conn, event_type, final_note, clip_path, zone_name=event_zone, risk_score=risk_score, event_class=event_class, metadata=metadata)
                    if event_zone:
                        record_zone_event(conn, event_zone, event_type, final_note, risk_score, event_class=event_class, metadata=metadata)

                    alert_message = build_alert_message(
                        event_type=event_type,
                        event_class=event_class,
                        zone_name=event_zone,
                        risk_score=risk_score,
                        note=final_note,
                    )
                    send_alert_notifications(pb, alert_message, channels=["pushbullet", "email", "sms", "whatsapp"])
                    log_alert(
                        conn,
                        event_type=event_type,
                        event_class=event_class,
                        zone_name=event_zone,
                        risk_score=risk_score,
                        note=final_note,
                        priority=alert_message["priority"],
                        channels=["pushbullet", "email", "sms", "whatsapp"],
                    )

                    capturing_post = True
                    post_counter = post_buf_len
                    pending = {"post_frames": [], "clip_path": clip_path}

                if pending and capturing_post:
                    pending["post_frames"].append(frame.copy())
                    post_counter -= 1
                    if post_counter <= 0:
                        save_clip(list(ring), pending["post_frames"], pending["clip_path"], fps)
                        capturing_post, pending = False, None

                cv2.imshow(stream_label, annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            except Exception as exc:
                print(f"[Camera] Error processing {stream_label}: {exc}")
                break
    finally:
        cap.release()
        cv2.destroyWindow(stream_label)
        conn.close()


# =========================
# MAIN CAMERA LOOP
# =========================
def camera_loop():
    camera_sources = resolve_camera_sources()

    if not camera_sources:
        camera_sources = [CAM_INDEX]

    def build_pushbullet_client():
        api_key = str(API_KEY or "").strip()
        if not api_key:
            print("[PushBullet] No API key configured. Notifications are disabled.")
            return None
        try:
            return Pushbullet(api_key)
        except Exception as exc:
            print(f"[PushBullet] Invalid or expired API key: {exc}")
            return None

    if len(camera_sources) == 1:
        conn = init_db()
        pb = build_pushbullet_client()
        process_stream(camera_sources[0], conn, pb, "Shop Surveillance")
        return

    threads = []
    for idx, source in enumerate(camera_sources):
        label = f"Shop Surveillance - Camera {idx + 1}"
        conn = init_db()
        pb = build_pushbullet_client()
        thread = threading.Thread(target=process_stream, args=(source, conn, pb, label), daemon=True)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

# =========================
# START EVERYTHING
# =========================
if __name__ == "__main__":
    camera_loop()

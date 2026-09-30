import json
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

APP_HOST = os.getenv("THREAT_SURVEILLANCE_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("THREAT_SURVEILLANCE_PORT", "5000"))
DEBUG_MODE = os.getenv("THREAT_SURVEILLANCE_DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("THREAT_SURVEILLANCE_ENV", "development")

EVIDENCE_DIR = Path(
    os.getenv("THREAT_SURVEILLANCE_EVIDENCE_DIR", str(BASE_DIR / "backend" / "runs" / "evidence"))
).resolve()
DB_PATH = Path(
    os.getenv("THREAT_SURVEILLANCE_DB_PATH", str(BASE_DIR / "backend" / "runs" / "events.db"))
).resolve()
LOCATION_PATH = Path(
    os.getenv("THREAT_SURVEILLANCE_LOCATION_PATH", str(BASE_DIR / "backend" / "runs" / "location.json"))
).resolve()
BACKUP_DIR = Path(
    os.getenv("THREAT_SURVEILLANCE_BACKUP_DIR", str(BASE_DIR / "backend" / "runs" / "backups"))
).resolve()

CAM_INDEX = int(os.getenv("THREAT_SURVEILLANCE_CAMERA_INDEX", "0"))
CAMERA_SOURCES = os.getenv("THREAT_SURVEILLANCE_CAMERA_SOURCES", "").strip()
API_KEY = os.getenv("THREAT_SURVEILLANCE_API_KEY", "").strip()
GOOGLE_MAPS_KEY = os.getenv("THREAT_SURVEILLANCE_GOOGLE_MAPS_KEY", "").strip()
SECRET_KEY = os.getenv("THREAT_SURVEILLANCE_SECRET_KEY", secrets.token_hex(32))
ENABLE_DASHBOARD_AUTH = os.getenv("THREAT_SURVEILLANCE_ENABLE_AUTH", "false").lower() == "true"
DASHBOARD_USERNAME = os.getenv("THREAT_SURVEILLANCE_DASHBOARD_USERNAME", "admin").strip()
DASHBOARD_PASSWORD = os.getenv("THREAT_SURVEILLANCE_DASHBOARD_PASSWORD", "change-me-in-production").strip()
RETENTION_DAYS = int(os.getenv("THREAT_SURVEILLANCE_RETENTION_DAYS", "30"))

PERSON_WEIGHTS = Path(
    os.getenv("THREAT_SURVEILLANCE_PERSON_WEIGHT", str(BASE_DIR / "backend" / "weights" / "yolov10n.pt"))
).resolve()
WEAPON_WEIGHTS = Path(
    os.getenv("THREAT_SURVEILLANCE_WEAPON_WEIGHT", str(BASE_DIR / "backend" / "weights" / "weapon_yolo.pt"))
).resolve()

EMAIL_ALERTS_TO = os.getenv("THREAT_SURVEILLANCE_EMAIL_ALERTS_TO", "").strip()
SMS_ALERTS_TO = os.getenv("THREAT_SURVEILLANCE_SMS_ALERTS_TO", "").strip()
WHATSAPP_ALERTS_TO = os.getenv("THREAT_SURVEILLANCE_WHATSAPP_ALERTS_TO", "").strip()
ALERT_CHANNELS = [
    channel for channel in [
        "pushbullet" if API_KEY else None,
        "email" if EMAIL_ALERTS_TO else None,
        "sms" if SMS_ALERTS_TO else None,
        "whatsapp" if WHATSAPP_ALERTS_TO else None,
    ] if channel
]

DEFAULT_ZONE_LAYOUT = [
    {"name": "entrance", "x": 0.00, "y": 0.00, "w": 0.35, "h": 0.35},
    {"name": "cashier", "x": 0.35, "y": 0.00, "w": 0.30, "h": 0.35},
    {"name": "storage", "x": 0.00, "y": 0.38, "w": 0.42, "h": 0.35},
    {"name": "restricted", "x": 0.42, "y": 0.38, "w": 0.32, "h": 0.35},
    {"name": "exit", "x": 0.70, "y": 0.00, "w": 0.30, "h": 0.35},
]
ZONE_LAYOUT = json.loads(
    os.getenv("THREAT_SURVEILLANCE_ZONES", json.dumps(DEFAULT_ZONE_LAYOUT))
)

EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOCATION_PATH.parent.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

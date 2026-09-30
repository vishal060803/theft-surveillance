import base64
import os
import sqlite3
from threading import Thread

import geocoder
from flask import Flask, Response, jsonify, request, send_file, send_from_directory

import config
import backend.realtime_surveillance as realtime

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_authorized_request():
    if not config.ENABLE_DASHBOARD_AUTH:
        return True

    provided_api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if config.API_KEY and provided_api_key == config.API_KEY:
        return True

    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("basic "):
        try:
            encoded = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
            if username == config.DASHBOARD_USERNAME and password == config.DASHBOARD_PASSWORD:
                return True
        except Exception:
            return False

    return False


@app.before_request
def require_dashboard_auth():
    allowed_routes = {"login", "health", "location", "auth_status", "system_health", "system_retention", "system_backup"}
    if request.endpoint in allowed_routes:
        return None

    if request.path.startswith("/static"):
        return None

    if request.path.startswith("/media/"):
        if not _is_authorized_request():
            return Response("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Theft Surveillance"'})
        return None

    if request.path.startswith("/") and not _is_authorized_request():
        return Response("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Theft Surveillance"'})

    return None


def start_detection():
    realtime.camera_loop()


@app.route("/")
def dashboard():
    template_path = os.path.join(BASE_DIR, "backend", "dashboard.html")
    with open(template_path, "r", encoding="utf-8") as handle:
        content = handle.read()
    rendered = content.replace("__GOOGLE_MAPS_KEY__", config.GOOGLE_MAPS_KEY)
    return rendered


@app.route("/auth/status")
def auth_status():
    return jsonify({
        "enabled": config.ENABLE_DASHBOARD_AUTH,
        "username": config.DASHBOARD_USERNAME,
    })


@app.route("/system/health")
def system_health():
    return jsonify(realtime.get_system_health_snapshot())


@app.route("/system/backup")
def system_backup():
    try:
        result = realtime.create_evidence_backup(str(config.EVIDENCE_DIR), str(config.BACKUP_DIR))
        return jsonify({"status": "ok", "backup_path": result})
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)})


@app.route("/system/retention")
def system_retention():
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        result = realtime.apply_retention_policy(base_dir=str(config.EVIDENCE_DIR), conn=conn, retention_days=config.RETENTION_DAYS)
        conn.close()
        return jsonify({"status": "ok", "result": result})
    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)})


@app.route("/media/<path:filename>")
def media(filename):
    return send_from_directory(str(config.EVIDENCE_DIR), filename, mimetype="video/x-msvideo")


@app.route("/events")
def events():
    clips = sorted(f for f in os.listdir(config.EVIDENCE_DIR) if f.endswith(".mp4"))
    return jsonify(clips)


@app.route("/location")
def location():
    try:
        g = geocoder.ip("me")
        if g.ok and g.latlng:
            lat, lon = g.latlng
            return jsonify({"lat": lat, "lon": lon})
    except Exception:
        pass
    return jsonify({"lat": 12.9716, "lon": 77.5946})


@app.route("/hotspots")
def hotspots():
    try:
        data = realtime.get_zone_hotspots()
        return jsonify({"zones": data, "generated_at": realtime.now_iso()})
    except Exception as exc:
        return jsonify({"zones": [], "error": str(exc), "generated_at": realtime.now_iso()})


@app.route("/evidence")
def evidence():
    try:
        records = realtime.list_evidence(str(config.EVIDENCE_DIR))
        return jsonify({"evidence": records, "count": len(records)})
    except Exception as exc:
        return jsonify({"evidence": [], "count": 0, "error": str(exc)})


@app.route("/evidence/export")
def evidence_export():
    try:
        records = realtime.list_evidence(str(config.EVIDENCE_DIR))
        export_path = realtime.export_events_csv(records, os.path.join(str(config.EVIDENCE_DIR), "incident_export.csv"))
        return send_file(export_path, mimetype="text/csv", as_attachment=True, download_name="incident_export.csv")
    except Exception as exc:
        return jsonify({"error": str(exc)})


@app.route("/health")
def health():
    evidence_count = len(realtime.list_evidence(str(config.EVIDENCE_DIR)))
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        alert_count = len(realtime.list_alerts(conn))
        conn.close()
    except Exception:
        alert_count = 0
    return jsonify({
        "status": "ok",
        "timestamp": realtime.now_iso(),
        "evidence_count": evidence_count,
        "alerts_count": alert_count,
        "camera_sources": realtime.resolve_camera_sources() if hasattr(realtime, "resolve_camera_sources") else [],
        "monitoring_mode": "active",
    })


@app.route("/dashboard/summary")
def dashboard_summary():
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        alerts = realtime.list_alerts(conn)
        evidence = realtime.list_evidence(str(config.EVIDENCE_DIR))
        hotspots = realtime.get_zone_hotspots()
        summary = realtime.build_incident_summary(conn)
        conn.close()
        high_risk = sum(1 for item in alerts if str(item.get("priority") or "").lower() in {"high", "critical"})
        return jsonify({
            "timestamp": realtime.now_iso(),
            "alerts_total": len(alerts),
            "alerts_high_risk": high_risk,
            "evidence_total": len(evidence),
            "zones_active": len(hotspots),
            "hotspots": hotspots,
            "latest_alert": alerts[0] if alerts else None,
            "incident_summary": summary,
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "alerts_total": 0, "alerts_high_risk": 0, "evidence_total": 0, "zones_active": 0, "hotspots": [], "incident_summary": {"total_events": 0, "by_event_type": {}, "by_zone": {}, "avg_risk": 0.0, "high_risk_events": 0}})


@app.route("/reports")
def reports():
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        summary = realtime.build_incident_summary(conn)
        daily = realtime.get_report_window_data(conn, window="day")
        weekly = realtime.get_report_window_data(conn, window="week")
        monthly = realtime.get_report_window_data(conn, window="month")
        conn.close()
        return jsonify({
            "summary": summary,
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
        })
    except Exception as exc:
        return jsonify({"error": str(exc), "summary": {"total_events": 0, "by_event_type": {}, "by_zone": {}, "avg_risk": 0.0}, "daily": [], "weekly": [], "monthly": []})


@app.route("/reports/export")
def reports_export():
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        data = realtime.get_report_window_data(conn, window="day")
        conn.close()
        export_path = realtime.export_report_csv(data, os.path.join(str(config.EVIDENCE_DIR), "report_export.csv"))
        return send_file(export_path, mimetype="text/csv", as_attachment=True, download_name="report_export.csv")
    except Exception as exc:
        return jsonify({"error": str(exc)})


@app.route("/validation")
def validation_report():
    try:
        result = realtime.run_validation_suite(
            true_positives=20,
            false_positives=2,
            false_negatives=4,
            lighting_score=0.8,
            crowd_density=0.7,
            video_quality=0.7,
            detection_ms=240,
            alert_ms=500,
            review_ms=210,
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc), "overall_status": "needs_attention"})


@app.route("/alerts")
def alerts():
    try:
        conn = sqlite3.connect(str(config.DB_PATH))
        data = realtime.list_alerts(conn)
        conn.close()
        return jsonify({"alerts": data, "count": len(data)})
    except Exception as exc:
        return jsonify({"alerts": [], "count": 0, "error": str(exc)})


@app.route("/alerts/<int:alert_id>/ack", methods=["POST"])
def acknowledge_alert(alert_id):
    try:
        payload = request.get_json(silent=True) or {}
        responder = payload.get("responder") or payload.get("name") or "security"
        conn = sqlite3.connect(str(config.DB_PATH))
        result = realtime.acknowledge_alert(conn, alert_id, responder)
        conn.close()
        return jsonify(result)
    except Exception as exc:
        return jsonify({"acknowledged": False, "error": str(exc)})


if __name__ == "__main__":
    config.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(config.EVIDENCE_DIR):
        os.makedirs(config.EVIDENCE_DIR, exist_ok=True)

    detection_thread = Thread(target=start_detection, daemon=True)
    detection_thread.start()
    app.run(host=config.APP_HOST, port=config.APP_PORT, debug=config.DEBUG_MODE)

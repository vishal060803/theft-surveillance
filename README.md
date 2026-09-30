# Crime Hotspot Detection and Theft Surveillance

A Python/OpenCV surveillance prototype that processes webcam or RTSP camera feeds, detects selected events with YOLO and MediaPipe, records incident metadata and evidence, and provides a Flask dashboard for alerts, hotspot summaries, system health, and reports.

> This is a prototype, not a certified security or emergency-response system. Validate camera access, model behavior, privacy, and local legal requirements before relying on it operationally.

## Highlights

- Webcam, USB camera, and RTSP/IP camera inputs
- Person detection and tracking; optional weapon model when its weight file is available
- Emergency open-palm gesture detection and optional violence heuristic
- Zone activity and risk/event summaries
- SQLite event and alert records, with evidence clips and JSON metadata
- Flask dashboard and JSON endpoints for health, alerts, evidence, reports, and validation
- Optional Pushbullet notifications and optional Google Maps dashboard view
- Environment-based configuration and Docker files

## Processing Workflow

1. Configure a webcam index or RTSP URL.
2. Start `app.py`; it starts the camera-processing thread and Flask web server.
3. OpenCV reads frames and runs the enabled detection/tracking logic.
4. When an event qualifies, the system writes an event record and evidence metadata, and records a clip when capture completes.
5. The dashboard reads events, alerts, evidence, and zone summaries from SQLite and the evidence directory.
6. Optional notification/map integrations run only when configured.

## Project Layout

```text
app.py                         Flask app and API routes; starts detection
config.py                      Environment-based settings and data paths
backend/realtime_surveillance.py  Camera processing, detection, database, alerts
backend/dashboard.html          Browser dashboard
backend/weights/               Model weight files
backend/runs/                  Local database, location, and evidence data
requirements.txt               Python dependencies
plan.md                        Development roadmap
 tests/                         Automated phase tests
Dockerfile                      Container image definition
docker-compose.yml              Container orchestration example
```

## Requirements

- Windows, Linux, or macOS; Windows instructions are shown below
- Python 3.11 recommended (the Docker image uses Python 3.11)
- A webcam/USB camera or a reachable RTSP camera/NVR
- Network access to download Python dependencies
- A compatible model weight file; the person model defaults to `backend/weights/yolov10n.pt`. Weapon detection is skipped if the configured weapon weights file is absent.

## Run Locally on Windows

Open Command Prompt in the folder where you want the project, then:

```cmd
git clone https://github.com/vishal060803/theft-surveillance.git
cd theft-surveillance
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Test with the laptop webcam

Set the camera source and start the app from the same Command Prompt window:

```cmd
set THREAT_SURVEILLANCE_CAMERA_SOURCES=0
set THREAT_SURVEILLANCE_CAMERA_INDEX=0
python app.py
```

Open [http://localhost:5000](http://localhost:5000). The processed camera view is opened by OpenCV in a separate window; the browser dashboard displays monitoring data and summaries.

### Test with an RTSP camera

Use the RTSP URL supplied by the camera/NVR configuration. The IP address alone is not an RTSP URL. Replace the placeholders with your camera's actual account, address, port, and stream path:

```cmd
set THREAT_SURVEILLANCE_CAMERA_SOURCES=rtsp://USERNAME:PASSWORD@CAMERA_IP:554/STREAM_PATH
set THREAT_SURVEILLANCE_CAMERA_INDEX=-1
python app.py
```

For example, if your NVR is `192.168.0.101`, do not assume its stream path or login: confirm these in its RTSP/stream settings or vendor documentation. Setting the camera index to `-1` prevents the default webcam index from being added alongside the RTSP source. If credentials contain URL-reserved characters such as `@`, `:`, `/`, or `#`, URL-encode them before putting them in the RTSP URL.

To test more than one source, use comma-separated values:

```cmd
set THREAT_SURVEILLANCE_CAMERA_SOURCES=0,rtsp://USERNAME:PASSWORD@CAMERA_IP:554/STREAM_PATH
set THREAT_SURVEILLANCE_CAMERA_INDEX=-1
```

Environment variables set with `set` apply only to that Command Prompt session. Run camera tests from the same window where the variables were set. On PowerShell, use `$env:THREAT_SURVEILLANCE_CAMERA_SOURCES = '0'` instead.

## Configuration

`config.py` reads settings from environment variables when the process starts. Common settings:

| Variable | Purpose | Default |
| --- | --- | --- |
| `THREAT_SURVEILLANCE_CAMERA_SOURCES` | Comma-separated camera indices or RTSP URLs | Empty |
| `THREAT_SURVEILLANCE_CAMERA_INDEX` | Local camera index; set `-1` when only using explicit RTSP sources | `0` |
| `THREAT_SURVEILLANCE_HOST` | Flask bind address | `0.0.0.0` |
| `THREAT_SURVEILLANCE_PORT` | Flask port | `5000` |
| `THREAT_SURVEILLANCE_API_KEY` | Pushbullet key and optional API key for dashboard authentication | Empty |
| `THREAT_SURVEILLANCE_GOOGLE_MAPS_KEY` | Optional browser Maps key | Empty |
| `THREAT_SURVEILLANCE_ENABLE_AUTH` | Enable dashboard/API authentication | `false` |
| `THREAT_SURVEILLANCE_DASHBOARD_USERNAME` | Dashboard Basic Auth username | `admin` |
| `THREAT_SURVEILLANCE_DASHBOARD_PASSWORD` | Dashboard Basic Auth password | `change-me-in-production` |
| `THREAT_SURVEILLANCE_EVIDENCE_DIR` | Evidence output directory | `backend/runs/evidence` |
| `THREAT_SURVEILLANCE_DB_PATH` | SQLite database path | `backend/runs/events.db` |

See `.env.example` for additional settings. The local Python app does not load `.env` files automatically; set variables in the shell before starting it. Docker Compose loads a local `.env` file through its `env_file` setting.

## Dashboard and API

- Dashboard: `http://localhost:5000/`
- Health: `http://localhost:5000/health`
- System health/camera status: `http://localhost:5000/system/health`
- Dashboard summary: `http://localhost:5000/dashboard/summary`
- Alerts: `http://localhost:5000/alerts`
- Evidence listing: `http://localhost:5000/evidence`
- Reports: `http://localhost:5000/reports`
- Validation summary: `http://localhost:5000/validation`

## Run Tests

From the project root with the virtual environment activated:

```cmd
python -m unittest discover -s tests -v
```

Some startup/runtime paths require camera hardware and cannot be fully validated by unit tests. Test with the actual camera and stream URL before deployment.

## Docker

Create a local `.env` file for Compose configuration, configure the RTSP URL and any integrations, then run:

```cmd
docker compose up --build
```

The Compose file maps port 5000 and persists `backend/runs` and `backend/weights`. Camera access from Docker may require additional host/device/network configuration, and OpenCV's GUI preview may not be available inside a headless container; validate the target environment before using this deployment mode.

## Troubleshooting

- **Camera cannot open:** test the exact RTSP URL in a media player such as VLC, confirm RTSP is enabled, and verify the PC can reach the camera/NVR and port. For a laptop webcam, test index `0` and check Windows camera privacy permissions.
- **RTSP source also opens webcam:** set `THREAT_SURVEILLANCE_CAMERA_INDEX=-1` when using explicit RTSP sources.
- **Dashboard shows no video:** the dashboard is not an embedded live video player; OpenCV displays the processed camera in a separate window.
- **Pushbullet errors:** set a valid `THREAT_SURVEILLANCE_API_KEY`; notifications are unavailable without one.
- **Map unavailable:** set a valid Google Maps browser key in `THREAT_SURVEILLANCE_GOOGLE_MAPS_KEY`; the dashboard remains usable without it.
- **Missing model file:** confirm the configured model weight path exists. Weapon detection is optional and disabled when its weight file is missing.

## Security and Privacy Notes

- Never commit `.env` files, real API keys, RTSP usernames/passwords, or private camera URLs.
- Treat recorded footage and database files as sensitive personal data. Store them securely, restrict access, and apply an appropriate retention policy.
- Change default dashboard credentials before enabling authentication or exposing the service beyond a trusted local network.
- Do not expose camera/NVR RTSP ports directly to the public internet.

## Project Status

The repository contains a phased roadmap in `plan.md` and automated tests for the implemented phases. Camera performance, detection quality, and false-alarm rates depend on the camera, scene, hardware, and model weights and require real-world validation.

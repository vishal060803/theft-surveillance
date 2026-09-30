Theft Surveillance / Crime Hotspot Detection Project

Overview
This project is a surveillance and crime detection system designed for a shop or commercial environment. It combines computer vision, event detection, alerting, and dashboard monitoring to identify suspicious activity and generate evidence clips for review.

The project is not a fully finished product yet. It is a partially completed prototype that demonstrates the workflow of:
- live camera monitoring,
- person and weapon detection,
- suspicious activity detection,
- personalized emergency signal detection,
- event recording,
- alert notifications,
- web dashboard integration,
- location tracking.

Project Goal
The main purpose of the project is to detect suspicious behavior or dangerous events in a monitored area and alert the owner or security team in near real time. The system captures short video clips of the event and presents them through a dashboard.

The system is conceptually built around a surveillance model where a camera monitors the location, detects abnormal or threatening activity, and reports it quickly.

What the project currently does
The implemented code suggests the following flow:
1. A camera stream is opened from the local machine.
2. Frames are processed using YOLO-based object detection.
3. Person detection and weapon detection are checked.
4. Motion-based violence detection is analyzed using frame difference.
5. MediaPipe Hand detection checks for emergency open-palm gestures.
6. If any event matches the risk conditions, the system saves a short clip.
7. The clip is stored in the evidence folder.
8. A PushBullet notification is sent.
9. A dashboard fetches the saved clips and displays them.
10. The current shop location is fetched and shown on a map.

Project Components

1. Flask Web App
File: app.py
Purpose:
- Hosts the dashboard and backend routes.
- Serves the evidence video clips.
- Exposes the /events, /media, and /location APIs.
- Starts the real-time surveillance process in a background thread.

Key role:
This acts as the main server layer that connects the video detection system to the web interface.

2. Surveillance Engine
File: backend/realtime_surveillance.py
Purpose:
- Captures live frames from the camera.
- Runs computer vision detection logic.
- Detects events and saves evidence.

Important features:
- Uses OpenCV for webcam access and image processing.
- Loads YOLO models for object detection.
- Detects people and weapons.
- Detects violent motion by comparing grayscale frame differences.
- Detects emergency open-palm gestures using MediaPipe Hands.
- Stores event metadata in SQLite.
- Saves captured clips in backend/runs/evidence.
- Sends PushBullet notifications.
- Writes current GPS location to backend/runs/location.json.

This is the core intelligence layer of the project.

3. Dashboard Frontend
File: backend/dashboard.html
Purpose:
- Displays a map for the monitored area.
- Shows saved video clips from the evidence folder.
- Polls the backend for new events.

Behavior:
- Fetches /events every 5 seconds.
- Loads only .mp4 files.
- Appends new clips to the page without duplicating earlier ones.
- Fetches /location and loads it into a Google Map.

This file is the web UI for monitoring suspicious events.

4. Data and Storage Components
- backend/runs/evidence: stores recorded event clips.
- backend/runs/location.json: stores latest coordinates.
- backend/runs/events.db: SQLite database for event records.

These storage layers allow the system to maintain event history and evidence files.

5. Model and Weight Files
Folders/files:
- backend/weights/
- backend/model/

Purpose:
- Contains trained or pre-trained YOLO weights used for detection.
- The real-time surveillance logic expects detection models such as YOLO weights for people and weapon recognition.

6. Notification System
Technology used: PushBullet
Purpose:
- Sends alerts to a connected PushBullet account when suspicious activity is detected.
- Also sends a Google Maps link with live coordinates when an event is triggered.

This is useful for immediate user awareness.

7. Utility and Experiment Scripts
Files:
- backend/weather_detect_video.py
- backend/sample_test_video.py
- backend/push_button_test.py
- backend/utils.py

Purpose:
- Test model behavior on sample video files.
- Test object detection and event logic.
- Experiment with person, weapon, motion, and emergency alert logic.
- Hold reusable logic or helper methods.

8. Frontend Folder
Files:
- frontend/index.html
- frontend/script.js
- frontend/style.css

Status:
These files are currently empty. The active dashboard is presently served from backend/dashboard.html instead of the frontend folder. This suggests the project is partly migrated or still under development.

Detection Logic in the Current Project
The current code performs several detection modes:

A. Person detection
- YOLO is used to detect people in the frame.
- It sets a confidence threshold.
- The system identifies if a person is present in the monitored area.

B. Weapon detection
- A second YOLO model is used for weapons.
- If a weapon is detected, the event is marked as WEAPON_DETECTED.

C. Violence / suspicious motion detection
- The system converts frames to grayscale and compares them to a previous frame.
- If the difference is large enough, it interprets the motion as possible aggressive action.
- This is a simple heuristic, not a deep action-recognition model.

D. Emergency signal detection
- MediaPipe Hands is used to detect hands in the frame.
- If the system recognizes an open palm with five fingers, it marks an EMERGENCY_SIGNAL event.
- This is designed to allow a shop owner to trigger a help request in an emergency.

E. Event handling
- When a relevant event occurs, the code captures a clip of the preceding frames and subsequent frames.
- It logs the event and saves the clip in the evidence folder.
- It triggers a PushBullet alert.

Project Workflow Summary
A simplified flow is:
Camera -> Frame Processing -> Object Detection -> Risk Assessment -> Event Trigger -> Save Clip -> Notify User -> Display in Dashboard

Architecture Overview
This project follows a simple layered architecture:

1. Input Layer
- Camera feed
- Optional sample videos

2. Detection Layer
- YOLO object detection
- Motion analysis
- Hand gesture detection

3. Event Layer
- Event classification
- Event logging
- Clip saving

4. Alert Layer
- Push notifications
- event updates

5. Interface Layer
- Flask APIs
- Google Map dashboard
- video list display

6. Storage Layer
- local video files
- SQLite event database
- JSON location file

Current State of the Project
The project is in a partial prototype stage. It includes a functioning concept and code for core detection and alert components, but some parts are still incomplete or inconsistent.

Examples of partial/incomplete areas:
- README is empty or missing proper documentation.
- Frontend folder is empty and not yet used.
- Some file paths and model names are inconsistent.
- App.py and the surveillance script both handle related endpoints independently.
- Some model names/files referenced in code may not exist or may need cleanup.
- There is no final polished UI or complete product-level structure.

This means the project is not fully production-ready, but it clearly demonstrates the intended idea and architecture for a surveillance-based crime hotspot system.

Possible Future Improvements
- clean and unify the backend API structure,
- complete the frontend web interface,
- improve object detection with a more reliable crime-related model,
- add real hotspot mapping and heatmap visualization,
- store events in a proper database with timestamps and metadata,
- integrate CCTV footage or live RTSP streams,
- add login, admin dashboard, and report generation,
- refine alert logic to reduce false positives,
- deploy the app in a real server environment.

Final Summary
This project is a computer-vision-based surveillance system for detecting suspicious activities in a shop or commercial space. It uses YOLO for person and weapon detection, MediaPipe for hand gesture detection, OpenCV for video processing, Flask for the server, SQLite for event logs, and a dashboard for displaying video evidence and location. The project is a promising prototype with a functioning event-driven detection pipeline, but it still requires cleanup and further development to become a complete, realistic, production-ready system.

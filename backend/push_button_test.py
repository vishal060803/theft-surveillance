import cv2
from ultralytics import YOLO
from pushbullet import Pushbullet
import mediapipe as mp
import os

# -----------------------
# CONFIG
# -----------------------
API_KEY = os.getenv("THREAT_SURVEILLANCE_API_KEY", "").strip()
if not API_KEY:
    raise SystemExit("Set THREAT_SURVEILLANCE_API_KEY before running this test.")
pb = Pushbullet(API_KEY)

# Load YOLOv10 (custom weights for weapons if available)
person_model = YOLO("backend/yolov10n.pt")   # detects people
weapon_model = YOLO("backend/weapon_yolov8.pt")  # custom trained for weapons

# Violence detection (placeholder, can integrate action model)
# For now → basic "fast motion" heuristic
motion_history = []

# MediaPipe Hands for owner emergency signal
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5)

# Video path
video_path = "../dataset/normal/video1.mp4"

# Alerts folder
os.makedirs("alerts", exist_ok=True)
frame_count = 0

# -----------------------
# Helper: Send PushBullet Alert
# -----------------------
def send_alert(title, message, frame, frame_count):
    alert_file = f"alerts/alert_frame_{frame_count}.jpg"
    cv2.imwrite(alert_file, frame)
    pb.push_note(title, message)
    with open(alert_file, "rb") as pic:
        file_data = pb.upload_file(pic, "alert.jpg")
        pb.push_file(**file_data)
    print(f"🚨 {title} | {message}")

# -----------------------
# VIDEO LOOP
# -----------------------
cap = cv2.VideoCapture(video_path)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    frame_count += 1

    # 1. Person + Weapon Detection
    results_person = person_model(frame, classes=[0], conf=0.5)
    results_weapon = weapon_model(frame, conf=0.5)

    annotated_frame = frame.copy()

    # Weapons found
    if results_weapon and len(results_weapon[0].boxes) > 0:
        send_alert("⚠️ Weapon Detected!", "Possible armed person in shop.", frame, frame_count)

    # 2. Violence Detection (simple motion heuristic for now)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    motion_history.append(gray)

    if len(motion_history) > 2:
        diff = cv2.absdiff(motion_history[-1], motion_history[-2])
        motion_score = cv2.countNonZero(diff)
        if motion_score > 50000:  # threshold for high activity
            send_alert("⚠️ Violence Detected!", "Unusual aggressive motion found!", frame, frame_count)
        if len(motion_history) > 3:
            motion_history.pop(0)

    # 3. Owner Safety Signal (open palm with 5 fingers)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results_hand = hands.process(rgb_frame)

    if results_hand.multi_hand_landmarks:
        for hand_landmarks in results_hand.multi_hand_landmarks:
            finger_tips = [8, 12, 16, 20]  # index, middle, ring, pinky tips
            thumb_tip = 4
            fingers_up = 0

            # Count open fingers
            if hand_landmarks.landmark[thumb_tip].x < hand_landmarks.landmark[2].x:
                fingers_up += 1
            for tip in finger_tips:
                if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[tip - 2].y:
                    fingers_up += 1

            if fingers_up == 5:
                send_alert("🚨 EMERGENCY SIGNAL!", "Owner requested help (5-finger safety sign).", frame, frame_count)

    # Show for debugging (optional)
    cv2.imshow("Shop Surveillance", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("✅ Monitoring Finished")

from ultralytics import YOLO

# -----------------------------
# Load YOLOv10 nano model (fastest on CPU)
# -----------------------------
model = YOLO("yolov10n.pt")

# Video path
video_path = "../dataset/normal/video1.mp4"

# -----------------------------
# Detection + tracking
# -----------------------------
results = model.track(
    source=video_path,
    tracker="bytetrack.yaml",
    show=True,       # display live video
    save=True,       # save output video in runs/track/
    classes=[0],     # detect only persons
    imgsz=416,       # smaller frame size for faster CPU processing
    device="cpu",
    conf=0.4,        # confidence threshold
    stream=True      # stream frames for memory efficiency
)

# -----------------------------
# Count unique person IDs with frame skipping
# -----------------------------
unique_ids = set()
frame_count = 0
frame_skip = 1  # process every 2nd frame for speed

for frame_result in results:
    frame_count += 1
    if frame_count % frame_skip != 0:
        continue
    if frame_result.boxes.id is not None:
        ids = frame_result.boxes.id.int().tolist()
        unique_ids.update(ids)

# -----------------------------
# Print result
# -----------------------------
print("✅ Tracking completed.")
print(f"👥 Total unique persons detected: {len(unique_ids)}")

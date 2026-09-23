from ultralytics import YOLO
m = YOLO("backend/models/best.pt")
print(m.names)

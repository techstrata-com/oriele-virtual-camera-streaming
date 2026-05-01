import type { Camera } from "../types/camera";

type Props = {
  camera: Camera;
};

export default function CameraPreview({ camera }: Props) {
  return (
    <div className="panel">
      <h2>Preview / consumer example</h2>
      <div className="muted" style={{ marginBottom: 10 }}>
        This MVP exposes the camera as a Linux video device. To view it, use another app
        that can read from <code>{camera.device_path}</code>.
      </div>
      <pre
        style={{
          margin: 0,
          padding: 12,
          borderRadius: 12,
          border: "1px solid rgba(255,255,255,0.12)",
          background: "rgba(0,0,0,0.18)",
          overflowX: "auto",
        }}
      >{`import cv2

cap = cv2.VideoCapture("${camera.device_path}")

while True:
    ret, frame = cap.read()
    if not ret:
        continue
    print(frame.shape)
`}</pre>
    </div>
  );
}


import type { Camera } from "../types/camera";

type Props = {
  camera: Camera;
};

export default function CameraPreview({ camera }: Props) {
  const canPreview = (camera.status === "running" || camera.status === "paused") && !!camera.http_live_url;
  const cacheBuster = camera.updated_at ? encodeURIComponent(camera.updated_at) : "";
  const src = camera.http_live_url ? `${camera.http_live_url}${camera.http_live_url.includes("?") ? "&" : "?"}t=${cacheBuster}` : "";

  return (
    <div className="panel">
      <h2>HTTP live preview</h2>
      {!canPreview && (
        <div className="muted">
          {camera.status === "starting"
            ? "Stream is starting..."
            : camera.status === "failed"
              ? "Stream failed. Check backend logs."
              : "Start the stream to preview it."}
        </div>
      )}

      {canPreview && (
        <div>
          <div className="muted" style={{ marginBottom: 10 }}>
            {camera.status === "paused" ? "Paused — preview should hold the last frame." : "Live MJPEG preview from the backend."}
          </div>
          <img
            src={src}
            alt={`${camera.name} preview`}
            style={{
              width: "100%",
              maxHeight: 420,
              objectFit: "contain",
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.12)",
              background: "rgba(0,0,0,0.18)",
            }}
          />
        </div>
      )}
    </div>
  );
}


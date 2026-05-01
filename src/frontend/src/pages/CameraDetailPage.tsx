import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCamera, restartCamera, startCamera, stopCamera } from "../api/cameras";
import { getVideo } from "../api/videos";
import type { Camera } from "../types/camera";
import type { Video } from "../types/video";
import CameraPreview from "../components/CameraPreview";

export default function CameraDetailPage() {
  const { cameraId } = useParams();
  const [camera, setCamera] = useState<Camera | null>(null);
  const [video, setVideo] = useState<Video | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!cameraId) return;
    setError(null);
    try {
      const cam = await getCamera(cameraId);
      setCamera(cam);
      const vid = await getVideo(cam.video_id);
      setVideo(vid);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to load camera.");
    }
  }

  useEffect(() => {
    refresh();
  }, [cameraId]);

  const statusBadge = useMemo(() => {
    if (!camera) return null;
    const cls =
      camera.status === "running"
        ? "badge running"
        : camera.status === "failed"
          ? "badge failed"
          : "badge";
    return <span className={cls}>{camera.status}</span>;
  }, [camera]);

  async function onCopy(text: string) {
    await navigator.clipboard.writeText(text);
  }

  async function onStart() {
    if (!camera) return;
    setCamera(await startCamera(camera.id));
  }
  async function onStop() {
    if (!camera) return;
    setCamera(await stopCamera(camera.id));
  }
  async function onRestart() {
    if (!camera) return;
    setCamera(await restartCamera(camera.id));
  }

  return (
    <div className="container">
      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <div className="muted" style={{ fontSize: 13 }}>
              <Link to="/cameras">← Back to Cameras</Link>
            </div>
            <div style={{ marginTop: 6 }}>
              <b style={{ fontSize: 18 }}>{camera?.name ?? "Camera"}</b>{" "}
              {statusBadge}
            </div>
          </div>
          <div className="row">
            <button className="btn primary" onClick={onStart} disabled={camera?.status === "running"}>
              Start
            </button>
            <button className="btn" onClick={onStop} disabled={camera?.status !== "running"}>
              Stop
            </button>
            <button className="btn" onClick={onRestart} disabled={!camera}>
              Restart
            </button>
            <button className="btn" onClick={refresh}>
              Refresh
            </button>
          </div>
        </div>

        {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}

        {camera && (
          <div style={{ marginTop: 12 }} className="grid">
            <div className="panel">
              <h2>Camera details</h2>
              <div className="muted">Device: <code>{camera.device_path}</code></div>
              <div className="muted">PID: {camera.pid ?? "—"}</div>
              <div className="muted">FPS: {camera.fps ?? "—"}</div>
              <div className="muted">
                Resolution: {camera.width && camera.height ? `${camera.width}x${camera.height}` : "—"}
              </div>
              <div className="muted">Loop: {camera.loop ? "Yes" : "No"}</div>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn" onClick={() => onCopy(camera.device_path)}>
                  Copy device path
                </button>
              </div>
            </div>
            <div className="panel">
              <h2>Video</h2>
              <div><b>{video?.name ?? "—"}</b></div>
              <div className="muted">{video?.original_filename ?? ""}</div>
              <div className="muted" style={{ marginTop: 8 }}>
                {video?.width && video?.height ? `${video.width}x${video.height}` : "—"}{" "}
                {video?.fps ? `@ ${video.fps.toFixed(2)} fps` : ""}
              </div>
              <div className="muted">
                Duration: {video?.duration ? `${video.duration.toFixed(2)}s` : "—"}
              </div>
            </div>
          </div>
        )}
      </div>

      {camera && <div style={{ marginTop: 16 }}><CameraPreview camera={camera} /></div>}
    </div>
  );
}


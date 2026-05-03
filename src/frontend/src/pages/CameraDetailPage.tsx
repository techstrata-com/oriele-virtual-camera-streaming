import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getCamera, pauseCamera, restartCamera, resumeCamera, startCamera, stopCamera } from "../api/cameras";
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
        : camera.status === "paused"
          ? "badge paused"
          : camera.status === "starting"
            ? "badge starting"
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
  async function onPause() {
    if (!camera) return;
    setCamera(await pauseCamera(camera.id));
  }
  async function onResume() {
    if (!camera) return;
    setCamera(await resumeCamera(camera.id));
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
            <button
              className="btn primary"
              onClick={onStart}
              disabled={!camera || camera.status === "running" || camera.status === "paused" || camera.status === "starting"}
            >
              Start
            </button>
            <button
              className="btn"
              onClick={onStop}
              disabled={!camera || !(camera.status === "running" || camera.status === "paused" || camera.status === "starting")}
            >
              Stop
            </button>
            <button className="btn" onClick={onPause} disabled={!camera || camera.status !== "running"}>
              Pause
            </button>
            <button className="btn" onClick={onResume} disabled={!camera || camera.status !== "paused"}>
              Resume
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
              <h2>Stream session</h2>
              <div className="muted">
                Client: <code>{camera.client_id ?? "—"}</code>
              </div>
              <div className="muted">RTSP worker PID: {camera.rtsp_pid ?? "—"}</div>
              <div className="muted">FPS: {camera.fps ?? "—"}</div>
              <div className="muted">
                Resolution: {camera.width && camera.height ? `${camera.width}x${camera.height}` : "—"}
              </div>
              <div className="muted">Loop: {camera.loop ? "Yes" : "No"}</div>

              <div style={{ marginTop: 10 }}>
                <div className="muted" style={{ marginBottom: 6 }}>
                  RTSP URL
                </div>
                {(camera.status === "running" || camera.status === "paused") && camera.rtsp_url ? (
                  <div className="row">
                    <code style={{ wordBreak: "break-all" }}>{camera.rtsp_url}</code>
                    <button className="btn sm" onClick={() => onCopy(camera.rtsp_url!)}>
                      Copy
                    </button>
                  </div>
                ) : (
                  <div className="muted">Not available</div>
                )}
              </div>

              <div style={{ marginTop: 10 }}>
                <div className="muted" style={{ marginBottom: 6 }}>
                  HTTP live URL
                </div>
                {(camera.status === "running" || camera.status === "paused") && camera.http_live_url ? (
                  <div className="row">
                    <code style={{ wordBreak: "break-all" }}>{camera.http_live_url}</code>
                    <button className="btn sm" onClick={() => onCopy(camera.http_live_url!)}>
                      Copy
                    </button>
                    <button className="btn sm" onClick={() => window.open(camera.http_live_url!, "_blank", "noopener,noreferrer")}>
                      Open
                    </button>
                  </div>
                ) : (
                  <div className="muted">Not available</div>
                )}
              </div>

              {(camera.device_path || camera.device_label || camera.pid) && (
                <details style={{ marginTop: 12 }}>
                  <summary className="muted" style={{ cursor: "pointer" }}>Legacy / debug</summary>
                  <div className="muted" style={{ marginTop: 8 }}>
                    device_label: {camera.device_label ?? "—"}
                  </div>
                  <div className="muted" style={{ marginTop: 6 }}>
                    device_path: <code>{camera.device_path ?? "—"}</code>
                  </div>
                  <div className="muted" style={{ marginTop: 6 }}>
                    pid: {camera.pid ?? "—"}
                  </div>
                </details>
              )}
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


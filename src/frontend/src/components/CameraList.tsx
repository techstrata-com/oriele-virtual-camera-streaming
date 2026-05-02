import { Link } from "react-router-dom";
import { useState } from "react";
import type { Camera } from "../types/camera";
import { deleteCamera, restartCamera, startCamera, stopCamera } from "../api/cameras";

type Props = {
  cameras: Camera[];
  videoNameById: Record<string, string>;
  onChanged: (camera: Camera) => void;
  onDeleted: (cameraId: string) => void;
};

function statusClass(status: string): string {
  if (status === "running") return "badge running";
  if (status === "failed") return "badge failed";
  return "badge";
}

export default function CameraList({ cameras, videoNameById, onChanged, onDeleted }: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  async function runRowAction(id: string, action: string, fn: () => Promise<void>) {
    setBusyId(id);
    setBusyAction(action);
    try {
      await fn();
    } finally {
      setBusyId(null);
      setBusyAction(null);
    }
  }

  async function onStart(id: string) {
    await runRowAction(id, "start", async () => {
      const cam = await startCamera(id);
      onChanged(cam);
    });
  }
  async function onStop(id: string) {
    await runRowAction(id, "stop", async () => {
      const cam = await stopCamera(id);
      onChanged(cam);
    });
  }
  async function onRestart(id: string) {
    await runRowAction(id, "restart", async () => {
      const cam = await restartCamera(id);
      onChanged(cam);
    });
  }
  async function onDelete(id: string) {
    if (!confirm("Delete this camera? If running, it will be stopped.")) return;
    await runRowAction(id, "delete", async () => {
      await deleteCamera(id);
      onDeleted(id);
    });
  }
  async function onCopy(text: string) {
    await navigator.clipboard.writeText(text);
  }
  function onOpen(url: string) {
    window.open(url, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="panel cameras-panel">
      <h2>Cameras</h2>

      <div className="camera-list">
        {cameras.map((c) => {
          const rowBusy = busyId === c.id;
          return (
            <div className="camera-row" key={c.id}>
              <div className="camera-main">
                <div className="camera-title">
                  <Link to={`/cameras/${c.id}`} className="camera-name">
                    <b>{c.name}</b>
                  </Link>
                  <span className={statusClass(c.status)}>{c.status}</span>
                </div>

                <div className="camera-sub muted">
                  <span className="camera-sub-item">
                    <span className="camera-sub-label">Video</span> {videoNameById[c.video_id] ?? c.video_id}
                  </span>
                  <span className="camera-sub-item">
                    <span className="camera-sub-label">Client</span> {c.client_id ?? "—"}
                  </span>
                  <span className="camera-sub-item">
                    <span className="camera-sub-label">PID</span> {c.pid ?? "—"}
                  </span>
                </div>

                <div className="camera-meta">
                  <div className="camera-meta-item">
                    <span className="camera-meta-label">Device</span>
                    <span className="mono" style={{ wordBreak: "break-all" }}>
                      {c.device_label ? (
                        <>
                          {c.device_label}{" "}
                          <span className="muted">({c.device_path})</span>
                        </>
                      ) : (
                        <code>{c.device_path}</code>
                      )}
                    </span>
                    <button className="btn sm" onClick={() => onCopy(c.device_path)} disabled={rowBusy}>
                      Copy path
                    </button>
                  </div>

                  <div className="camera-meta-item muted">
                    <span className="camera-meta-label">Output</span>
                    {c.width && c.height ? `${c.width}×${c.height}` : "—"}{" "}
                    {c.fps ? `@ ${c.fps.toFixed(2)} fps` : ""}
                  </div>
                </div>
              </div>

              <div className="camera-streams">
                <div className="stream-block">
                  <div className="stream-header">
                    <span className="stream-label">RTSP</span>
                    {c.status === "running" && c.rtsp_url ? (
                      <span className="stream-pill ok">ready</span>
                    ) : (
                      <span className="stream-pill">—</span>
                    )}
                  </div>
                  {c.status === "running" && c.rtsp_url ? (
                    <>
                      <code className="stream-url" title={c.rtsp_url}>
                        {c.rtsp_url}
                      </code>
                      <div className="stream-actions">
                        <button className="btn sm" onClick={() => onCopy(c.rtsp_url!)} disabled={rowBusy}>
                          Copy
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="muted stream-empty">Not available</div>
                  )}
                </div>

                <div className="stream-block">
                  <div className="stream-header">
                    <span className="stream-label">HTTP Live</span>
                    {c.status === "running" && c.http_live_url ? (
                      <span className="stream-pill ok">ready</span>
                    ) : (
                      <span className="stream-pill">—</span>
                    )}
                  </div>
                  {c.status === "running" && c.http_live_url ? (
                    <>
                      <code className="stream-url" title={c.http_live_url}>
                        {c.http_live_url}
                      </code>
                      <div className="stream-actions">
                        <button className="btn sm" onClick={() => onCopy(c.http_live_url!)} disabled={rowBusy}>
                          Copy
                        </button>
                        <button className="btn sm" onClick={() => onOpen(c.http_live_url!)} disabled={rowBusy}>
                          Open
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="muted stream-empty">Not available</div>
                  )}
                </div>
              </div>

              <div className="camera-actions actions-group">
                <button
                  className="btn primary sm"
                  onClick={() => onStart(c.id)}
                  disabled={rowBusy || c.status === "running"}
                  title="Start camera"
                >
                  {rowBusy && busyAction === "start" ? "Starting…" : "Start"}
                </button>
                <button
                  className="btn sm"
                  onClick={() => onStop(c.id)}
                  disabled={rowBusy || c.status !== "running"}
                  title="Stop camera"
                >
                  {rowBusy && busyAction === "stop" ? "Stopping…" : "Stop"}
                </button>
                <button
                  className="btn sm"
                  onClick={() => onRestart(c.id)}
                  disabled={rowBusy}
                  title="Restart camera"
                >
                  {rowBusy && busyAction === "restart" ? "Restarting…" : "Restart"}
                </button>
                <button
                  className="btn danger sm"
                  onClick={() => onDelete(c.id)}
                  disabled={rowBusy}
                  title="Delete camera"
                >
                  {rowBusy && busyAction === "delete" ? "Deleting…" : "Delete"}
                </button>
              </div>
            </div>
          );
        })}

        {cameras.length === 0 && <div className="muted" style={{ padding: 10 }}>No cameras created yet.</div>}
      </div>
    </div>
  );
}


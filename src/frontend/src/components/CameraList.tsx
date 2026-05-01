import { Link } from "react-router-dom";
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
  async function onStart(id: string) {
    const cam = await startCamera(id);
    onChanged(cam);
  }
  async function onStop(id: string) {
    const cam = await stopCamera(id);
    onChanged(cam);
  }
  async function onRestart(id: string) {
    const cam = await restartCamera(id);
    onChanged(cam);
  }
  async function onDelete(id: string) {
    if (!confirm("Delete this camera? If running, it will be stopped.")) return;
    await deleteCamera(id);
    onDeleted(id);
  }
  async function onCopy(text: string) {
    await navigator.clipboard.writeText(text);
  }

  return (
    <div className="panel">
      <h2>Cameras</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Video</th>
            <th>Device</th>
            <th>Status</th>
            <th>PID</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {cameras.map((c) => (
            <tr key={c.id}>
              <td>
                <div>
                  <Link to={`/cameras/${c.id}`}>
                    <b>{c.name}</b>
                  </Link>
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {c.width && c.height ? `${c.width}x${c.height}` : "—"}{" "}
                  {c.fps ? `@ ${c.fps.toFixed(2)} fps` : ""}
                </div>
              </td>
              <td className="muted">{videoNameById[c.video_id] ?? c.video_id}</td>
              <td>
                <code>{c.device_path}</code>{" "}
                <button className="btn" onClick={() => onCopy(c.device_path)}>
                  Copy
                </button>
              </td>
              <td>
                <span className={statusClass(c.status)}>{c.status}</span>
              </td>
              <td className="muted">{c.pid ?? "—"}</td>
              <td>
                <div className="row">
                  <button className="btn primary" onClick={() => onStart(c.id)} disabled={c.status === "running"}>
                    Start
                  </button>
                  <button className="btn" onClick={() => onStop(c.id)} disabled={c.status !== "running"}>
                    Stop
                  </button>
                  <button className="btn" onClick={() => onRestart(c.id)}>
                    Restart
                  </button>
                  <button className="btn danger" onClick={() => onDelete(c.id)}>
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {cameras.length === 0 && (
            <tr>
              <td colSpan={6} className="muted" style={{ padding: 14 }}>
                No cameras created yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}


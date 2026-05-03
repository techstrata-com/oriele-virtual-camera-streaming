import { useEffect, useMemo, useState } from "react";
import type { Video } from "../types/video";
import type { Camera, CameraCreate } from "../types/camera";
import { createCamera } from "../api/cameras";
import { getOrCreateClientId } from "../utils/clientId";

type Props = {
  videos: Video[];
  defaultVideoId?: string;
  onCreated: (camera: Camera) => void;
};

export default function CameraForm({ videos, defaultVideoId, onCreated }: Props) {
  const clientId = useMemo(() => getOrCreateClientId(), []);
  const defaultId = useMemo(() => defaultVideoId ?? videos[0]?.id ?? "", [defaultVideoId, videos]);
  const [name, setName] = useState("");
  const [videoId, setVideoId] = useState(defaultId);
  const [fps, setFps] = useState<string>("30");
  const [width, setWidth] = useState<string>("1280");
  const [height, setHeight] = useState<string>("720");
  const [loop, setLoop] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!videoId && defaultId) setVideoId(defaultId);
  }, [defaultId, videoId]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (!videoId) {
      setError("Select a video first.");
      return;
    }
    if (!name.trim()) {
      setError("Camera name is required.");
      return;
    }
    setBusy(true);
    try {
      const payload: CameraCreate = {
        client_id: clientId,
        name: name.trim(),
        video_id: videoId,
        device_path: null, // deprecated; keep for backend compatibility
        fps: fps ? Number(fps) : null,
        width: width ? Number(width) : null,
        height: height ? Number(height) : null,
        loop,
      };
      const cam = await createCamera(payload);
      onCreated(cam);
      setSuccess("Stream session ready.");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to create camera.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h2>Create stream session</h2>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label>Client ID</label>
          <div className="muted" style={{ fontSize: 13, wordBreak: "break-all" }}>
            <code>{clientId}</code>
          </div>
          <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
            Used to reuse the same stream session when you create again for the same video.
          </div>
        </div>
        <div className="field">
          <label>Video</label>
          <select value={videoId} onChange={(e) => setVideoId(e.target.value)}>
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Session name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Entry Gate Camera" />
        </div>
        <div className="grid" style={{ marginTop: 0 }}>
          <div className="field">
            <label>FPS</label>
            <input value={fps} onChange={(e) => setFps(e.target.value)} placeholder="30" />
          </div>
          <div className="field">
            <label>Loop</label>
            <select value={loop ? "yes" : "no"} onChange={(e) => setLoop(e.target.value === "yes")}>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
        </div>
        <div className="grid" style={{ marginTop: 0 }}>
          <div className="field">
            <label>Width</label>
            <input value={width} onChange={(e) => setWidth(e.target.value)} placeholder="1280" />
          </div>
          <div className="field">
            <label>Height</label>
            <input value={height} onChange={(e) => setHeight(e.target.value)} placeholder="720" />
          </div>
        </div>
        <div className="row">
          <button className="btn primary" disabled={busy || videos.length === 0} type="submit">
            {busy ? "Creating..." : "Create"}
          </button>
          <span className="muted">Stream URLs appear after Start.</span>
        </div>
      </form>
      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}
      {success && <div className="success" style={{ marginTop: 10 }}>{success}</div>}
    </div>
  );
}

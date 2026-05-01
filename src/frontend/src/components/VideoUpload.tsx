import { useState } from "react";
import { uploadVideo } from "../api/videos";
import type { Video } from "../types/video";

type Props = {
  onUploaded: (video: Video) => void;
};

export default function VideoUpload({ onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const v = await uploadVideo(file);
      onUploaded(v);
      setFile(null);
      (document.getElementById("video-file") as HTMLInputElement | null)?.value &&
        ((document.getElementById("video-file") as HTMLInputElement).value = "");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h2>Upload video</h2>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label>Video file</label>
          <input
            id="video-file"
            type="file"
            accept="video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <div className="row">
          <button className="btn primary" disabled={!file || busy} type="submit">
            {busy ? "Uploading..." : "Upload"}
          </button>
          <span className="muted">
            Files will be stored in <code>data/videos/&lt;id&gt;/</code>
          </span>
        </div>
      </form>
      {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}
    </div>
  );
}


import type { Video } from "../types/video";
import { deleteVideo } from "../api/videos";
import { thumbnailUrl } from "../api/videos";

function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

type Props = {
  videos: Video[];
  onDeleted: (videoId: string) => void;
  onCreateCamera: (video: Video) => void;
};

export default function VideoList({ videos, onDeleted, onCreateCamera }: Props) {
  async function onDelete(videoId: string) {
    if (!confirm("Delete this video? Cameras using it will block deletion.")) return;
    await deleteVideo(videoId);
    onDeleted(videoId);
  }

  return (
    <div className="panel">
      <h2>Videos</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Thumbnail</th>
            <th>Name</th>
            <th>Metadata</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {videos.map((v) => (
            <tr key={v.id}>
              <td>
                {v.thumbnail_path ? (
                  <img className="thumb" src={thumbnailUrl(v.id)} alt={v.name} />
                ) : (
                  <div className="thumb" />
                )}
              </td>
              <td>
                <div>
                  <b>{v.name}</b>
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {v.original_filename}
                </div>
              </td>
              <td>
                <div className="muted">
                  {v.width && v.height ? `${v.width}x${v.height}` : "—"}{" "}
                  {v.fps ? `@ ${v.fps.toFixed(2)} fps` : ""}
                </div>
                <div className="muted">
                  {v.duration ? `${v.duration.toFixed(2)}s` : "—"} ·{" "}
                  {formatBytes(v.size_bytes)}
                </div>
              </td>
              <td>
                <div className="row">
                  <button className="btn primary" onClick={() => onCreateCamera(v)}>
                    Create Camera
                  </button>
                  <button className="btn danger" onClick={() => onDelete(v.id)}>
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {videos.length === 0 && (
            <tr>
              <td colSpan={4} className="muted" style={{ padding: 14 }}>
                No videos uploaded yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}


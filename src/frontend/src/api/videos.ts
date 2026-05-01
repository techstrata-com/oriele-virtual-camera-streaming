import { api } from "./client";
import type { Video } from "../types/video";

export async function uploadVideo(file: File): Promise<Video> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<Video>("/api/videos/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function listVideos(): Promise<Video[]> {
  const res = await api.get<Video[]>("/api/videos");
  return res.data;
}

export async function getVideo(videoId: string): Promise<Video> {
  const res = await api.get<Video>(`/api/videos/${videoId}`);
  return res.data;
}

export async function deleteVideo(videoId: string): Promise<void> {
  await api.delete(`/api/videos/${videoId}`);
}

export function thumbnailUrl(videoId: string): string {
  return `${api.defaults.baseURL}/api/videos/${videoId}/thumbnail`;
}


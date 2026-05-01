import { api } from "./client";
import type { Camera, CameraCreate } from "../types/camera";

export async function createCamera(payload: CameraCreate): Promise<Camera> {
  const res = await api.post<Camera>("/api/cameras", payload);
  return res.data;
}

export async function listCameras(): Promise<Camera[]> {
  const res = await api.get<Camera[]>("/api/cameras");
  return res.data;
}

export async function getCamera(cameraId: string): Promise<Camera> {
  const res = await api.get<Camera>(`/api/cameras/${cameraId}`);
  return res.data;
}

export async function startCamera(cameraId: string): Promise<Camera> {
  const res = await api.post<Camera>(`/api/cameras/${cameraId}/start`);
  return res.data;
}

export async function stopCamera(cameraId: string): Promise<Camera> {
  const res = await api.post<Camera>(`/api/cameras/${cameraId}/stop`);
  return res.data;
}

export async function restartCamera(cameraId: string): Promise<Camera> {
  const res = await api.post<Camera>(`/api/cameras/${cameraId}/restart`);
  return res.data;
}

export async function deleteCamera(cameraId: string): Promise<void> {
  await api.delete(`/api/cameras/${cameraId}`);
}


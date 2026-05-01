export type Video = {
  id: string;
  name: string;
  original_filename: string;
  file_path: string;
  thumbnail_path?: string | null;
  duration?: number | null;
  fps?: number | null;
  width?: number | null;
  height?: number | null;
  size_bytes: number;
  created_at: string;
  updated_at: string;
};


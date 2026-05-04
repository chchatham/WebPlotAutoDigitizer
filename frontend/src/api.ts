const API_BASE = import.meta.env.VITE_API_URL ?? "";

export interface UploadResponse {
  image_id: string;
  width: number;
  height: number;
  filename: string;
}

export async function uploadImage(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export interface Calibration {
  x_pixel_range: [number, number];
  y_pixel_range: [number, number];
  x_data_range: [number, number];
  y_data_range: [number, number];
  detection_bounds?: { x_min: number; x_max: number; y_min: number; y_max: number };
  expected_point_count?: number | null;
}

export interface DetectAxesResponse {
  axes: Calibration;
  confidence: number;
}

export async function detectAxes(imageId: string): Promise<DetectAxesResponse> {
  const res = await fetch(`${API_BASE}/api/detect-axes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_id: imageId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Axis detection failed");
  }
  return res.json();
}

export interface DetectedPoint {
  x_data: number;
  y_data: number;
  x_pixel: number;
  y_pixel: number;
  confidence: number;
}

export interface DigitizeResponse {
  points: DetectedPoint[];
  method: string;
  elapsed_ms: number;
}

export async function digitize(
  imageId: string,
  calibration: Calibration,
): Promise<DigitizeResponse> {
  const { detection_bounds, expected_point_count, ...cal } = calibration;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/digitize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_id: imageId,
        calibration: cal,
        detection_bounds: detection_bounds ?? null,
        expected_point_count: expected_point_count ?? null,
      }),
    });
  } catch (e) {
    throw new Error(
      `Network error: ${e instanceof Error ? e.message : "could not reach server"}`,
    );
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `Server error (${res.status})`);
  }

  let data: DigitizeResponse;
  try {
    data = await res.json();
  } catch {
    throw new Error("Invalid response from server (malformed JSON)");
  }

  if (!data || !Array.isArray(data.points)) {
    throw new Error("Invalid response: missing points array");
  }

  return data;
}

export function getImageUrl(imageId: string): string {
  return `${API_BASE}/api/image/${imageId}`;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

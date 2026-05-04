import { useEffect, useState, useRef } from "react";
import { digitize, getImageUrl, type Calibration, type UploadResponse, type DigitizeResponse } from "../api";
import CsvExport from "./CsvExport";

interface Props {
  upload: UploadResponse;
  calibration: Calibration;
  onBack: () => void;
  onReset: () => void;
}

export default function ResultsView({ upload, calibration, onBack, onReset }: Props) {
  const [result, setResult] = useState<DigitizeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    setLoading(true);
    digitize(upload.image_id, calibration)
      .then(setResult)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [upload.image_id, calibration]);

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      setScale(Math.min(1, 760 / img.width));
    };
    img.src = getImageUrl(upload.image_id);
  }, [upload.image_id]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image || !result) return;

    const ctx = canvas.getContext("2d")!;
    canvas.width = image.width * scale;
    canvas.height = image.height * scale;

    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

    for (const pt of result.points) {
      const x = pt.x_pixel * scale;
      const y = pt.y_pixel * scale;

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(220, 38, 38, ${0.3 + pt.confidence * 0.7})`;
      ctx.fill();
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }, [image, result, scale]);

  if (loading) return <p>Digitizing...</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Error: {error}</p>;
  if (!result) return null;

  return (
    <div>
      <h2>Detected Points</h2>
      <p style={{ color: "#6b7280", fontSize: 14 }}>
        Method: {result.method} | {result.points.length} points | {result.elapsed_ms.toFixed(0)}ms
      </p>

      <canvas ref={canvasRef} style={{ border: "1px solid #e5e7eb" }} />

      <CsvExport points={result.points} />

      <div style={{ maxHeight: 300, overflow: "auto", marginTop: 16, border: "1px solid #e5e7eb", borderRadius: 8 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f8fafc", position: "sticky", top: 0 }}>
              <th style={{ padding: "8px 12px", textAlign: "left" }}>#</th>
              <th style={{ padding: "8px 12px", textAlign: "right" }}>X</th>
              <th style={{ padding: "8px 12px", textAlign: "right" }}>Y</th>
              <th style={{ padding: "8px 12px", textAlign: "right" }}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {result.points.map((pt, i) => (
              <tr key={i} style={{ borderTop: "1px solid #e5e7eb" }}>
                <td style={{ padding: "6px 12px" }}>{i + 1}</td>
                <td style={{ padding: "6px 12px", textAlign: "right", fontFamily: "monospace" }}>
                  {pt.x_data.toFixed(4)}
                </td>
                <td style={{ padding: "6px 12px", textAlign: "right", fontFamily: "monospace" }}>
                  {pt.y_data.toFixed(4)}
                </td>
                <td style={{ padding: "6px 12px", textAlign: "right" }}>
                  {(pt.confidence * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <button onClick={onBack}>Adjust calibration</button>
        <button onClick={onReset} style={{ background: "transparent", border: "1px solid #94a3b8" }}>
          New image
        </button>
      </div>
    </div>
  );
}

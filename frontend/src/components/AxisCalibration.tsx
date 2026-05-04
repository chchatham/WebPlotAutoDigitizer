import { useEffect, useState, useRef, useCallback } from "react";
import { detectAxes, getImageUrl, type Calibration, type UploadResponse } from "../api";

interface Props {
  upload: UploadResponse;
  onCalibrated: (calibration: Calibration) => void;
  onBack: () => void;
}

type Handle = "xMin" | "xMax" | "yMin" | "yMax";

export default function AxisCalibrationView({ upload, onCalibrated, onBack }: Props) {
  const [calibration, setCalibration] = useState<Calibration | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<Handle | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);

  const [xMinVal, setXMinVal] = useState("0");
  const [xMaxVal, setXMaxVal] = useState("10");
  const [yMinVal, setYMinVal] = useState("0");
  const [yMaxVal, setYMaxVal] = useState("10");

  useEffect(() => {
    setLoading(true);
    detectAxes(upload.image_id)
      .then((res) => {
        setCalibration(res.axes);
        setXMinVal(String(res.axes.x_data_range[0]));
        setXMaxVal(String(res.axes.x_data_range[1]));
        setYMinVal(String(res.axes.y_data_range[0]));
        setYMaxVal(String(res.axes.y_data_range[1]));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [upload.image_id]);

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      const maxWidth = 760;
      setScale(Math.min(1, maxWidth / img.width));
    };
    img.onerror = () => {
      const fallbackCanvas = document.createElement("canvas");
      fallbackCanvas.width = upload.width;
      fallbackCanvas.height = upload.height;
      const ctx = fallbackCanvas.getContext("2d")!;
      ctx.fillStyle = "#e5e7eb";
      ctx.fillRect(0, 0, upload.width, upload.height);
      ctx.fillStyle = "#6b7280";
      ctx.font = "16px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Image preview unavailable", upload.width / 2, upload.height / 2);
      const fallback = new Image();
      fallback.src = fallbackCanvas.toDataURL();
      fallback.onload = () => {
        setImage(fallback);
        setScale(Math.min(1, 760 / upload.width));
      };
    };
    img.src = getImageUrl(upload.image_id);
  }, [upload]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !image || !calibration) return;

    const ctx = canvas.getContext("2d")!;
    canvas.width = image.width * scale;
    canvas.height = image.height * scale;

    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

    const [xMinPx, xMaxPx] = calibration.x_pixel_range;
    const [yMinPx, yMaxPx] = calibration.y_pixel_range;

    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);

    // X-axis line (bottom)
    ctx.beginPath();
    ctx.moveTo(xMinPx * scale, yMinPx * scale);
    ctx.lineTo(xMaxPx * scale, yMinPx * scale);
    ctx.stroke();

    // Y-axis line (left)
    ctx.beginPath();
    ctx.moveTo(xMinPx * scale, yMinPx * scale);
    ctx.lineTo(xMinPx * scale, yMaxPx * scale);
    ctx.stroke();

    ctx.setLineDash([]);

    const handles: { handle: Handle; x: number; y: number }[] = [
      { handle: "xMin", x: xMinPx * scale, y: yMinPx * scale },
      { handle: "xMax", x: xMaxPx * scale, y: yMinPx * scale },
      { handle: "yMin", x: xMinPx * scale, y: yMinPx * scale },
      { handle: "yMax", x: xMinPx * scale, y: yMaxPx * scale },
    ];

    for (const h of handles) {
      ctx.fillStyle = dragging === h.handle ? "#dc2626" : "#2563eb";
      ctx.beginPath();
      ctx.arc(h.x, h.y, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "white";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }, [image, calibration, scale, dragging]);

  const onMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!calibration) return;
      const rect = canvasRef.current!.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const [xMinPx, xMaxPx] = calibration.x_pixel_range;
      const [yMinPx, yMaxPx] = calibration.y_pixel_range;

      const handles: { handle: Handle; x: number; y: number }[] = [
        { handle: "xMin", x: xMinPx * scale, y: yMinPx * scale },
        { handle: "xMax", x: xMaxPx * scale, y: yMinPx * scale },
        { handle: "yMax", x: xMinPx * scale, y: yMaxPx * scale },
      ];

      for (const h of handles) {
        if (Math.hypot(mx - h.x, my - h.y) < 12) {
          setDragging(h.handle);
          return;
        }
      }
    },
    [calibration, scale]
  );

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!dragging || !calibration) return;
      const rect = canvasRef.current!.getBoundingClientRect();
      const mx = (e.clientX - rect.left) / scale;
      const my = (e.clientY - rect.top) / scale;

      setCalibration((prev) => {
        if (!prev) return prev;
        const next = { ...prev };
        if (dragging === "xMin") {
          next.x_pixel_range = [mx, prev.x_pixel_range[1]];
          next.y_pixel_range = [my, prev.y_pixel_range[1]];
        } else if (dragging === "xMax") {
          next.x_pixel_range = [prev.x_pixel_range[0], mx];
        } else if (dragging === "yMax") {
          next.y_pixel_range = [prev.y_pixel_range[0], my];
        }
        return next;
      });
    },
    [dragging, calibration, scale]
  );

  const onMouseUp = useCallback(() => setDragging(null), []);

  const handleConfirm = () => {
    if (!calibration) return;
    const final: Calibration = {
      ...calibration,
      x_data_range: [parseFloat(xMinVal) || 0, parseFloat(xMaxVal) || 10],
      y_data_range: [parseFloat(yMinVal) || 0, parseFloat(yMaxVal) || 10],
    };
    onCalibrated(final);
  };

  if (loading) return <p>Detecting axes...</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Error: {error}</p>;

  return (
    <div>
      <h2>Adjust Axis Calibration</h2>
      <p>Drag the blue handles to align with the axis endpoints. Enter the data values below.</p>

      <canvas
        ref={canvasRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        style={{ cursor: dragging ? "grabbing" : "default", border: "1px solid #e5e7eb" }}
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16, maxWidth: 400 }}>
        <label>
          X min:
          <input type="number" step="any" value={xMinVal} onChange={(e) => setXMinVal(e.target.value)} />
        </label>
        <label>
          X max:
          <input type="number" step="any" value={xMaxVal} onChange={(e) => setXMaxVal(e.target.value)} />
        </label>
        <label>
          Y min:
          <input type="number" step="any" value={yMinVal} onChange={(e) => setYMinVal(e.target.value)} />
        </label>
        <label>
          Y max:
          <input type="number" step="any" value={yMaxVal} onChange={(e) => setYMaxVal(e.target.value)} />
        </label>
      </div>

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <button onClick={handleConfirm}>Confirm &amp; Digitize</button>
        <button onClick={onBack} style={{ background: "transparent", border: "1px solid #94a3b8" }}>
          Back
        </button>
      </div>
    </div>
  );
}

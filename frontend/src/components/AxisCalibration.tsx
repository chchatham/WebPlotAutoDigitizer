import { useEffect, useState, useRef, useCallback } from "react";
import { detectAxes, getImageUrl, type Calibration, type UploadResponse } from "../api";

interface Props {
  upload: UploadResponse;
  onCalibrated: (calibration: Calibration) => void;
  onBack: () => void;
}

interface HandlePos {
  x: number;
  y: number;
}

type HandleId = "xLeft" | "xRight" | "yBottom" | "yTop";

export default function AxisCalibrationView({ upload, onCalibrated, onBack }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<HandleId | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);

  const [xLeft, setXLeft] = useState<HandlePos>({ x: 0, y: 0 });
  const [xRight, setXRight] = useState<HandlePos>({ x: 0, y: 0 });
  const [yBottom, setYBottom] = useState<HandlePos>({ x: 0, y: 0 });
  const [yTop, setYTop] = useState<HandlePos>({ x: 0, y: 0 });

  const [xMinVal, setXMinVal] = useState("0");
  const [xMaxVal, setXMaxVal] = useState("10");
  const [yMinVal, setYMinVal] = useState("0");
  const [yMaxVal, setYMaxVal] = useState("10");

  useEffect(() => {
    setLoading(true);
    detectAxes(upload.image_id)
      .then((res) => {
        const ax = res.axes;
        const [xMinPx, xMaxPx] = ax.x_pixel_range;
        const [yMinPx, yMaxPx] = ax.y_pixel_range;
        // X-axis: horizontal line at bottom (yMinPx is the larger y = bottom)
        setXLeft({ x: xMinPx, y: yMinPx });
        setXRight({ x: xMaxPx, y: yMinPx });
        // Y-axis: vertical line at left (xMinPx)
        setYBottom({ x: xMinPx, y: yMinPx });
        setYTop({ x: xMinPx, y: yMaxPx });

        setXMinVal(String(ax.x_data_range[0]));
        setXMaxVal(String(ax.x_data_range[1]));
        setYMinVal(String(ax.y_data_range[0]));
        setYMaxVal(String(ax.y_data_range[1]));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [upload.image_id]);

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      setImage(img);
      setScale(Math.min(1, 760 / img.width));
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
    if (!canvas || !image) return;

    const ctx = canvas.getContext("2d")!;
    canvas.width = image.width * scale;
    canvas.height = image.height * scale;

    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);

    // X-axis line (blue)
    ctx.strokeStyle = "#2563eb";
    ctx.beginPath();
    ctx.moveTo(xLeft.x * scale, xLeft.y * scale);
    ctx.lineTo(xRight.x * scale, xRight.y * scale);
    ctx.stroke();

    // Y-axis line (green)
    ctx.strokeStyle = "#16a34a";
    ctx.beginPath();
    ctx.moveTo(yBottom.x * scale, yBottom.y * scale);
    ctx.lineTo(yTop.x * scale, yTop.y * scale);
    ctx.stroke();

    ctx.setLineDash([]);

    const handles: { id: HandleId; pos: HandlePos; color: string; label: string }[] = [
      { id: "xLeft", pos: xLeft, color: "#2563eb", label: "X min" },
      { id: "xRight", pos: xRight, color: "#2563eb", label: "X max" },
      { id: "yBottom", pos: yBottom, color: "#16a34a", label: "Y min" },
      { id: "yTop", pos: yTop, color: "#16a34a", label: "Y max" },
    ];

    for (const h of handles) {
      const sx = h.pos.x * scale;
      const sy = h.pos.y * scale;
      ctx.fillStyle = dragging === h.id ? "#dc2626" : h.color;
      ctx.beginPath();
      ctx.arc(sx, sy, 7, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "white";
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = "white";
      ctx.font = "bold 9px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(h.label, sx, sy);
    }
  }, [image, xLeft, xRight, yBottom, yTop, scale, dragging]);

  const onMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rect = canvasRef.current!.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const handles: { id: HandleId; pos: HandlePos }[] = [
        { id: "xLeft", pos: xLeft },
        { id: "xRight", pos: xRight },
        { id: "yBottom", pos: yBottom },
        { id: "yTop", pos: yTop },
      ];

      for (const h of handles) {
        if (Math.hypot(mx - h.pos.x * scale, my - h.pos.y * scale) < 14) {
          setDragging(h.id);
          return;
        }
      }
    },
    [xLeft, xRight, yBottom, yTop, scale]
  );

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!dragging) return;
      const rect = canvasRef.current!.getBoundingClientRect();
      const mx = (e.clientX - rect.left) / scale;
      const my = (e.clientY - rect.top) / scale;

      if (dragging === "xLeft") {
        setXLeft({ x: mx, y: my });
      } else if (dragging === "xRight") {
        setXRight({ x: mx, y: my });
      } else if (dragging === "yBottom") {
        setYBottom({ x: mx, y: my });
      } else if (dragging === "yTop") {
        setYTop({ x: mx, y: my });
      }
    },
    [dragging, scale]
  );

  const onMouseUp = useCallback(() => setDragging(null), []);

  const handleConfirm = () => {
    const cal: Calibration = {
      x_pixel_range: [xLeft.x, xRight.x],
      y_pixel_range: [
        Math.max(xLeft.y, yBottom.y),
        Math.min(xRight.y, yTop.y),
      ],
      x_data_range: [parseFloat(xMinVal) || 0, parseFloat(xMaxVal) || 10],
      y_data_range: [parseFloat(yMinVal) || 0, parseFloat(yMaxVal) || 10],
    };
    onCalibrated(cal);
  };

  if (loading) return <p>Detecting axes...</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Error: {error}</p>;

  return (
    <div>
      <h2>Adjust Axis Calibration</h2>
      <p style={{ fontSize: 14, color: "#6b7280" }}>
        Drag handles to align with axis endpoints.
        <span style={{ color: "#2563eb", fontWeight: 600 }}> Blue</span> = X-axis,
        <span style={{ color: "#16a34a", fontWeight: 600 }}> Green</span> = Y-axis.
      </p>

      <canvas
        ref={canvasRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        style={{ cursor: dragging ? "grabbing" : "default", border: "1px solid #e5e7eb" }}
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16, maxWidth: 400 }}>
        <label style={{ color: "#2563eb" }}>
          X min:
          <input type="number" step="any" value={xMinVal} onChange={(e) => setXMinVal(e.target.value)} />
        </label>
        <label style={{ color: "#2563eb" }}>
          X max:
          <input type="number" step="any" value={xMaxVal} onChange={(e) => setXMaxVal(e.target.value)} />
        </label>
        <label style={{ color: "#16a34a" }}>
          Y min:
          <input type="number" step="any" value={yMinVal} onChange={(e) => setYMinVal(e.target.value)} />
        </label>
        <label style={{ color: "#16a34a" }}>
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

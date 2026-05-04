import { useEffect, useState, useRef, useCallback } from "react";
import { detectAxes, getImageUrl, type Calibration, type UploadResponse } from "../api";

interface Props {
  upload: UploadResponse;
  onCalibrated: (calibration: Calibration) => void;
  onBack: () => void;
  previousCalibration?: Calibration | null;
}

type HandleId =
  | "xLeft" | "xRight" | "yBottom" | "yTop"
  | "xAxisLine" | "yAxisLine"
  | "bbTL" | "bbTR" | "bbBL" | "bbBR";

const HANDLE_RADIUS = 7;
const HIT_RADIUS = 14;
const ZOOM_SIZE = 200;
const ZOOM_FACTOR = 8;

export default function AxisCalibrationView({ upload, onCalibrated, onBack, previousCalibration }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<HandleId | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const zoomCanvasRef = useRef<HTMLCanvasElement>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);

  const [xLeftX, setXLeftX] = useState(0);
  const [xRightX, setXRightX] = useState(0);
  const [xAxisY, setXAxisY] = useState(0);

  const [yBottomY, setYBottomY] = useState(0);
  const [yTopY, setYTopY] = useState(0);
  const [yAxisX, setYAxisX] = useState(0);

  const [bbLeft, setBbLeft] = useState(0);
  const [bbRight, setBbRight] = useState(0);
  const [bbTop, setBbTop] = useState(0);
  const [bbBottom, setBbBottom] = useState(0);

  const [xMinVal, setXMinVal] = useState("0");
  const [xMaxVal, setXMaxVal] = useState("10");
  const [yMinVal, setYMinVal] = useState("0");
  const [yMaxVal, setYMaxVal] = useState("10");

  const [expectedPointCount, setExpectedPointCount] = useState("");

  const [activeHandle, setActiveHandle] = useState<HandleId | null>(null);
  const [activeHandlePos, setActiveHandlePos] = useState<{ x: number; y: number } | null>(null);
  const dragStartRef = useRef<{ mx: number; my: number; origVal: number } | null>(null);

  useEffect(() => {
    if (previousCalibration) {
      const [xMinPx, xMaxPx] = previousCalibration.x_pixel_range;
      const [yMinPx, yMaxPx] = previousCalibration.y_pixel_range;

      setXLeftX(xMinPx);
      setXRightX(xMaxPx);
      setXAxisY(yMinPx);

      setYAxisX(xMinPx);
      setYBottomY(yMinPx);
      setYTopY(yMaxPx);

      if (previousCalibration.detection_bounds) {
        const db = previousCalibration.detection_bounds;
        setBbLeft(db.x_min);
        setBbRight(db.x_max);
        setBbTop(db.y_min);
        setBbBottom(db.y_max);
      } else {
        const xSpan = xMaxPx - xMinPx;
        const ySpan = yMinPx - yMaxPx;
        setBbLeft(Math.max(0, xMinPx - xSpan * 0.15));
        setBbRight(Math.min(upload.width, xMaxPx + xSpan * 0.15));
        setBbTop(Math.max(0, yMaxPx - ySpan * 0.15));
        setBbBottom(Math.min(upload.height, yMinPx + ySpan * 0.15));
      }

      setXMinVal(String(previousCalibration.x_data_range[0]));
      setXMaxVal(String(previousCalibration.x_data_range[1]));
      setYMinVal(String(previousCalibration.y_data_range[0]));
      setYMaxVal(String(previousCalibration.y_data_range[1]));
      if (previousCalibration.expected_point_count) {
        setExpectedPointCount(String(previousCalibration.expected_point_count));
      }
      setLoading(false);
      return;
    }

    setLoading(true);
    detectAxes(upload.image_id)
      .then((res) => {
        const ax = res.axes;
        const [xMinPx, xMaxPx] = ax.x_pixel_range;
        const [yMinPx, yMaxPx] = ax.y_pixel_range;

        setXLeftX(xMinPx);
        setXRightX(xMaxPx);
        setXAxisY(yMinPx);

        setYAxisX(xMinPx);
        setYBottomY(yMinPx);
        setYTopY(yMaxPx);

        const xSpan = xMaxPx - xMinPx;
        const ySpan = yMinPx - yMaxPx;
        const imgW = upload.width;
        const imgH = upload.height;
        setBbLeft(Math.max(0, xMinPx - xSpan * 0.15));
        setBbRight(Math.min(imgW, xMaxPx + xSpan * 0.15));
        setBbTop(Math.max(0, yMaxPx - ySpan * 0.15));
        setBbBottom(Math.min(imgH, yMinPx + ySpan * 0.15));

        setXMinVal(String(ax.x_data_range[0]));
        setXMaxVal(String(ax.x_data_range[1]));
        setYMinVal(String(ax.y_data_range[0]));
        setYMaxVal(String(ax.y_data_range[1]));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [upload.image_id, previousCalibration]);

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

    // Bounding box (orange dashed)
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.strokeRect(
      bbLeft * scale, bbTop * scale,
      (bbRight - bbLeft) * scale, (bbBottom - bbTop) * scale,
    );
    ctx.setLineDash([]);

    // Bounding box corner handles (orange)
    const bbHandles: { id: HandleId; x: number; y: number }[] = [
      { id: "bbTL", x: bbLeft, y: bbTop },
      { id: "bbTR", x: bbRight, y: bbTop },
      { id: "bbBL", x: bbLeft, y: bbBottom },
      { id: "bbBR", x: bbRight, y: bbBottom },
    ];
    for (const h of bbHandles) {
      const sx = h.x * scale;
      const sy = h.y * scale;
      ctx.fillStyle = dragging === h.id ? "#dc2626" : "#d97706";
      ctx.fillRect(sx - 5, sy - 5, 10, 10);
      ctx.strokeStyle = "white";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(sx - 5, sy - 5, 10, 10);
    }

    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);

    // X-axis line (blue, horizontal)
    ctx.strokeStyle = "#2563eb";
    ctx.beginPath();
    ctx.moveTo(xLeftX * scale, xAxisY * scale);
    ctx.lineTo(xRightX * scale, xAxisY * scale);
    ctx.stroke();

    // Y-axis line (green, vertical)
    ctx.strokeStyle = "#16a34a";
    ctx.beginPath();
    ctx.moveTo(yAxisX * scale, yBottomY * scale);
    ctx.lineTo(yAxisX * scale, yTopY * scale);
    ctx.stroke();

    ctx.setLineDash([]);

    const handles: { id: HandleId; x: number; y: number; color: string; label: string }[] = [
      { id: "xLeft", x: xLeftX, y: xAxisY, color: "#2563eb", label: "X min" },
      { id: "xRight", x: xRightX, y: xAxisY, color: "#2563eb", label: "X max" },
      { id: "yBottom", x: yAxisX, y: yBottomY, color: "#16a34a", label: "Y min" },
      { id: "yTop", x: yAxisX, y: yTopY, color: "#16a34a", label: "Y max" },
    ];

    for (const h of handles) {
      const sx = h.x * scale;
      const sy = h.y * scale;
      ctx.fillStyle = dragging === h.id ? "#dc2626" : h.color;
      ctx.beginPath();
      ctx.arc(sx, sy, HANDLE_RADIUS, 0, Math.PI * 2);
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
  }, [image, xLeftX, xRightX, xAxisY, yAxisX, yBottomY, yTopY, bbLeft, bbRight, bbTop, bbBottom, scale, dragging]);

  // Zoom panel
  useEffect(() => {
    const zoomCanvas = zoomCanvasRef.current;
    if (!zoomCanvas || !image) return;

    const ctx = zoomCanvas.getContext("2d")!;
    zoomCanvas.width = ZOOM_SIZE;
    zoomCanvas.height = ZOOM_SIZE;

    if (!activeHandlePos) {
      ctx.fillStyle = "#f1f5f9";
      ctx.fillRect(0, 0, ZOOM_SIZE, ZOOM_SIZE);
      ctx.fillStyle = "#94a3b8";
      ctx.font = "13px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("Drag a handle to zoom", ZOOM_SIZE / 2, ZOOM_SIZE / 2);
      return;
    }

    const srcSize = ZOOM_SIZE / ZOOM_FACTOR;
    const srcX = activeHandlePos.x - srcSize / 2;
    const srcY = activeHandlePos.y - srcSize / 2;

    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(
      image,
      srcX, srcY, srcSize, srcSize,
      0, 0, ZOOM_SIZE, ZOOM_SIZE,
    );

    // Crosshairs
    ctx.strokeStyle = "rgba(220, 38, 38, 0.8)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(ZOOM_SIZE / 2, 0);
    ctx.lineTo(ZOOM_SIZE / 2, ZOOM_SIZE);
    ctx.moveTo(0, ZOOM_SIZE / 2);
    ctx.lineTo(ZOOM_SIZE, ZOOM_SIZE / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Center dot
    ctx.fillStyle = "rgba(220, 38, 38, 0.9)";
    ctx.beginPath();
    ctx.arc(ZOOM_SIZE / 2, ZOOM_SIZE / 2, 3, 0, Math.PI * 2);
    ctx.fill();

    // Label
    if (activeHandle) {
      const labelMap: Record<string, string> = {
        xLeft: "X min", xRight: "X max", yBottom: "Y min", yTop: "Y max",
        bbTL: "Box TL", bbTR: "Box TR", bbBL: "Box BL", bbBR: "Box BR",
        xAxisLine: "X-axis", yAxisLine: "Y-axis",
      };
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      ctx.fillRect(0, 0, ZOOM_SIZE, 20);
      ctx.fillStyle = "white";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillText(`${labelMap[activeHandle] ?? activeHandle} (${ZOOM_FACTOR}x zoom)`, ZOOM_SIZE / 2, 4);
    }
  }, [image, activeHandle, activeHandlePos]);

  const hitTestAxisLine = useCallback(
    (mx: number, my: number): HandleId | null => {
      const lineHitDist = 8;

      // X-axis line: horizontal at xAxisY, from xLeftX to xRightX
      if (
        mx >= xLeftX * scale + HIT_RADIUS &&
        mx <= xRightX * scale - HIT_RADIUS &&
        Math.abs(my - xAxisY * scale) < lineHitDist
      ) {
        return "xAxisLine";
      }

      // Y-axis line: vertical at yAxisX, from yTopY to yBottomY
      if (
        my >= yTopY * scale + HIT_RADIUS &&
        my <= yBottomY * scale - HIT_RADIUS &&
        Math.abs(mx - yAxisX * scale) < lineHitDist
      ) {
        return "yAxisLine";
      }

      return null;
    },
    [xLeftX, xRightX, xAxisY, yAxisX, yBottomY, yTopY, scale],
  );

  const onMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rect = canvasRef.current!.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      // Check axis handles first (they're on top)
      const axisHandles: { id: HandleId; x: number; y: number }[] = [
        { id: "xLeft", x: xLeftX, y: xAxisY },
        { id: "xRight", x: xRightX, y: xAxisY },
        { id: "yBottom", x: yAxisX, y: yBottomY },
        { id: "yTop", x: yAxisX, y: yTopY },
      ];
      for (const h of axisHandles) {
        if (Math.hypot(mx - h.x * scale, my - h.y * scale) < HIT_RADIUS) {
          setDragging(h.id);
          setActiveHandle(h.id);
          setActiveHandlePos({ x: h.x, y: h.y });
          return;
        }
      }

      // Then bounding box corners
      const bbCorners: { id: HandleId; x: number; y: number }[] = [
        { id: "bbTL", x: bbLeft, y: bbTop },
        { id: "bbTR", x: bbRight, y: bbTop },
        { id: "bbBL", x: bbLeft, y: bbBottom },
        { id: "bbBR", x: bbRight, y: bbBottom },
      ];
      for (const h of bbCorners) {
        if (Math.hypot(mx - h.x * scale, my - h.y * scale) < HIT_RADIUS) {
          setDragging(h.id);
          setActiveHandle(h.id);
          setActiveHandlePos({ x: h.x, y: h.y });
          return;
        }
      }

      // Then axis lines (drag to reposition shared coordinate)
      const lineHit = hitTestAxisLine(mx, my);
      if (lineHit) {
        setDragging(lineHit);
        setActiveHandle(lineHit);
        if (lineHit === "xAxisLine") {
          dragStartRef.current = { mx, my, origVal: xAxisY };
          setActiveHandlePos({ x: (xLeftX + xRightX) / 2, y: xAxisY });
        } else {
          dragStartRef.current = { mx, my, origVal: yAxisX };
          setActiveHandlePos({ x: yAxisX, y: (yTopY + yBottomY) / 2 });
        }
        return;
      }
    },
    [xLeftX, xRightX, xAxisY, yAxisX, yBottomY, yTopY, bbLeft, bbRight, bbTop, bbBottom, scale, hitTestAxisLine],
  );

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!dragging) return;
      const rect = canvasRef.current!.getBoundingClientRect();
      const mx = (e.clientX - rect.left) / scale;
      const my = (e.clientY - rect.top) / scale;

      let posX = mx;
      let posY = my;

      const imgW = image?.width ?? upload.width;
      const imgH = image?.height ?? upload.height;

      switch (dragging) {
        case "xLeft":
          setXLeftX(mx);
          setXAxisY(my);
          posY = my;
          break;
        case "xRight":
          setXRightX(mx);
          setXAxisY(my);
          posY = my;
          break;
        case "yBottom":
          setYBottomY(my);
          setYAxisX(mx);
          posX = mx;
          break;
        case "yTop":
          setYTopY(my);
          setYAxisX(mx);
          posX = mx;
          break;
        case "xAxisLine":
          setXAxisY(my);
          posX = (xLeftX + xRightX) / 2;
          posY = my;
          break;
        case "yAxisLine":
          setYAxisX(mx);
          posX = mx;
          posY = (yTopY + yBottomY) / 2;
          break;
        case "bbTL":
          setBbLeft(Math.max(0, mx));
          setBbTop(Math.max(0, my));
          break;
        case "bbTR":
          setBbRight(Math.min(imgW, mx));
          setBbTop(Math.max(0, my));
          break;
        case "bbBL":
          setBbLeft(Math.max(0, mx));
          setBbBottom(Math.min(imgH, my));
          break;
        case "bbBR":
          setBbRight(Math.min(imgW, mx));
          setBbBottom(Math.min(imgH, my));
          break;
      }

      setActiveHandlePos({ x: posX, y: posY });
    },
    [dragging, scale, xAxisY, yAxisX, xLeftX, xRightX, yTopY, yBottomY, image, upload],
  );

  const onMouseUp = useCallback(() => {
    setDragging(null);
    dragStartRef.current = null;
  }, []);

  const handleConfirm = () => {
    const parsedCount = parseInt(expectedPointCount, 10);
    const cal: Calibration = {
      x_pixel_range: [xLeftX, xRightX],
      y_pixel_range: [yBottomY, yTopY],
      x_data_range: [parseFloat(xMinVal) || 0, parseFloat(xMaxVal) || 10],
      y_data_range: [parseFloat(yMinVal) || 0, parseFloat(yMaxVal) || 10],
      detection_bounds: {
        x_min: Math.min(bbLeft, bbRight),
        x_max: Math.max(bbLeft, bbRight),
        y_min: Math.min(bbTop, bbBottom),
        y_max: Math.max(bbTop, bbBottom),
      },
      expected_point_count: !isNaN(parsedCount) && parsedCount > 0 ? parsedCount : null,
    };
    onCalibrated(cal);
  };

  if (loading) return <p>Detecting axes...</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Error: {error}</p>;

  return (
    <div>
      <h2>Adjust Axis Calibration</h2>
      <p style={{ fontSize: 14, color: "#6b7280", marginBottom: 8 }}>
        <span style={{ color: "#2563eb", fontWeight: 600 }}>Blue</span> handles = X-axis (drag to position; vertical movement shifts the whole axis).{" "}
        <span style={{ color: "#16a34a", fontWeight: 600 }}>Green</span> handles = Y-axis (drag to position; horizontal movement shifts the whole axis).
      </p>
      <p style={{ fontSize: 14, color: "#6b7280", marginBottom: 12 }}>
        <span style={{ color: "#d97706", fontWeight: 600 }}>Orange box</span> = detection area. Expand it to cover all data points, including any beyond the axis min/max values.
      </p>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <canvas
          ref={canvasRef}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          style={{ cursor: dragging ? "grabbing" : "default", border: "1px solid #e5e7eb", flexShrink: 0 }}
        />

        <div style={{ flexShrink: 0 }}>
          <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4, fontWeight: 600 }}>
            Precision Zoom
          </div>
          <canvas
            ref={zoomCanvasRef}
            width={ZOOM_SIZE}
            height={ZOOM_SIZE}
            style={{ border: "1px solid #e5e7eb", borderRadius: 4, imageRendering: "pixelated" }}
          />
        </div>
      </div>

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

      <div style={{ marginTop: 12, maxWidth: 400 }}>
        <label style={{ color: "#6b7280", fontSize: 14 }}>
          Expected number of points (optional):
          <input
            type="number"
            min="1"
            max="1000"
            step="1"
            placeholder="Leave blank for auto-detect"
            value={expectedPointCount}
            onChange={(e) => setExpectedPointCount(e.target.value)}
            style={{ marginLeft: 8, width: 180 }}
          />
        </label>
      </div>

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <button onClick={handleConfirm}>Confirm &amp; Digitize</button>
        <button onClick={onBack} style={{ background: "#f1f5f9", border: "1px solid #94a3b8", color: "#1e293b" }}>
          Back
        </button>
      </div>
    </div>
  );
}

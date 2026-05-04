import { useCallback } from "react";
import type { DetectedPoint } from "../api";

interface Props {
  points: DetectedPoint[];
}

function pointsToCsv(points: DetectedPoint[]): string {
  const header = "x,y,confidence";
  const rows = points.map((p) => `${p.x_data},${p.y_data},${p.confidence.toFixed(3)}`);
  return [header, ...rows].join("\n");
}

export default function CsvExport({ points }: Props) {
  const csv = pointsToCsv(points);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(csv);
  }, [csv]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "digitized_points.csv";
    a.click();
    URL.revokeObjectURL(url);
  }, [csv]);

  return (
    <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
      <button onClick={handleCopy}>Copy CSV</button>
      <button onClick={handleDownload}>Download CSV</button>
      <span style={{ color: "#6b7280", fontSize: 14, alignSelf: "center" }}>
        {points.length} points
      </span>
    </div>
  );
}

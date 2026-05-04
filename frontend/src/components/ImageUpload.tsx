import { useCallback, useState, useRef } from "react";
import { uploadImage, type UploadResponse } from "../api";

interface Props {
  onUploaded: (result: UploadResponse) => void;
}

export default function ImageUpload({ onUploaded }: Props) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setUploading(true);
      try {
        const result = await uploadImage(file);
        onUploaded(result);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [onUploaded]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      style={{
        border: `2px dashed ${dragging ? "#2563eb" : "#94a3b8"}`,
        borderRadius: 12,
        padding: 48,
        textAlign: "center",
        cursor: "pointer",
        background: dragging ? "#eff6ff" : "#f8fafc",
        transition: "all 0.15s",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        onChange={onFileChange}
        style={{ display: "none" }}
      />
      {uploading ? (
        <p>Uploading...</p>
      ) : (
        <p>
          Drag &amp; drop a scatterplot image here, or <strong>click to browse</strong>
          <br />
          <small>PNG, JPG, or WEBP — max 10 MB</small>
        </p>
      )}
      {error && <p style={{ color: "#dc2626", marginTop: 8 }}>{error}</p>}
    </div>
  );
}

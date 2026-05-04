import { useState } from "react";
import "./App.css";
import ImageUpload from "./components/ImageUpload";
import AxisCalibrationView from "./components/AxisCalibration";
import ResultsView from "./components/ResultsView";
import ErrorBoundary from "./components/ErrorBoundary";
import type { UploadResponse, Calibration } from "./api";

type Page = "digitizer" | "about";
type Step = "upload" | "calibrate" | "results";

function NavBar({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  return (
    <nav style={{
      display: "flex",
      alignItems: "center",
      gap: 24,
      marginBottom: 20,
      borderBottom: "1px solid #e5e7eb",
      paddingBottom: 12,
      padding: "12px 24px",
    }}>
      <h1 style={{ margin: 0, fontSize: "1.5rem", flex: 1, textAlign: "left" }}>WebPlot AutoDigitizer</h1>
      <button
        onClick={() => setPage("digitizer")}
        style={{
          background: page === "digitizer" ? "#2563eb" : "transparent",
          color: page === "digitizer" ? "white" : "#475569",
          border: page === "digitizer" ? "none" : "1px solid #cbd5e1",
          fontSize: 14,
          padding: "6px 16px",
        }}
      >
        Digitizer
      </button>
      <button
        onClick={() => setPage("about")}
        style={{
          background: page === "about" ? "#2563eb" : "transparent",
          color: page === "about" ? "white" : "#475569",
          border: page === "about" ? "none" : "1px solid #cbd5e1",
          fontSize: 14,
          padding: "6px 16px",
        }}
      >
        About
      </button>
    </nav>
  );
}

function App() {
  const [page, setPage] = useState<Page>("digitizer");
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [calibration, setCalibration] = useState<Calibration | null>(null);
  const [step, setStep] = useState<Step>("upload");

  const handleUploaded = (result: UploadResponse) => {
    setUpload(result);
    setStep("calibrate");
  };

  const handleCalibrated = (cal: Calibration) => {
    setCalibration(cal);
    setStep("results");
  };

  const reset = () => {
    setUpload(null);
    setCalibration(null);
    setStep("upload");
  };

  if (page === "about") {
    return (
      <div style={{ width: "100vw", minHeight: "100vh" }}>
        <NavBar page={page} setPage={setPage} />
        <iframe
          src="/about.html"
          style={{
            width: "100%",
            height: "calc(100vh - 80px)",
            border: "none",
            display: "block",
          }}
          title="About WebPlot AutoDigitizer"
        />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 24 }}>
      <NavBar page={page} setPage={setPage} />

      <p style={{ color: "#6b7280", marginBottom: 16 }}>
        Upload a scatterplot image to extract its data points as CSV.
      </p>

      <ErrorBoundary onReset={reset}>
        {step === "upload" && <ImageUpload onUploaded={handleUploaded} />}

        {step === "calibrate" && upload && (
          <AxisCalibrationView upload={upload} onCalibrated={handleCalibrated} onBack={reset} previousCalibration={calibration} />
        )}

        {step === "results" && upload && calibration && (
          <ResultsView
            upload={upload}
            calibration={calibration}
            onBack={() => setStep("calibrate")}
            onReset={reset}
          />
        )}
      </ErrorBoundary>
    </div>
  );
}

export default App;

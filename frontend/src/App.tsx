import { useState } from "react";
import "./App.css";
import ImageUpload from "./components/ImageUpload";
import AxisCalibrationView from "./components/AxisCalibration";
import ResultsView from "./components/ResultsView";
import type { UploadResponse, Calibration } from "./api";

type Step = "upload" | "calibrate" | "results";

function App() {
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

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: 24 }}>
      <h1>WebPlot AutoDigitizer</h1>
      <p>Upload a scatterplot image to extract its data points as CSV.</p>

      {step === "upload" && <ImageUpload onUploaded={handleUploaded} />}

      {step === "calibrate" && upload && (
        <AxisCalibrationView upload={upload} onCalibrated={handleCalibrated} onBack={reset} />
      )}

      {step === "results" && upload && calibration && (
        <ResultsView
          upload={upload}
          calibration={calibration}
          onBack={() => setStep("calibrate")}
          onReset={reset}
        />
      )}
    </div>
  );
}

export default App;

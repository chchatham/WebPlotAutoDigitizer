# WebPlot AutoDigitizer

Extract data points from scatterplot images as CSV. Upload an image, calibrate the axes, and download the digitized data.

## Features

- Drag-and-drop image upload (PNG, JPG, WEBP)
- Auto-detected axis lines with manual fiducial adjustment
- Hybrid digitization: blob detection + template matching
- Point overlay on original image
- Copy/download results as CSV
- CPU-only, no GPU required

## Quick Start

### Docker (recommended)

```bash
docker-compose up
# Open http://localhost:8000
```

### Local Development

**Backend:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

**Tests:**
```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Deployment

### Railway / Render / Fly.io

1. Push to a Git repository
2. Connect the repo to your hosting provider
3. Set the build command: `docker build -t app .`
4. Set the start command: `docker run -p 8000:8000 app`
5. The app serves both API and frontend on port 8000

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/upload` | POST | Upload plot image (multipart) |
| `/api/image/{id}` | GET | Retrieve uploaded image |
| `/api/detect-axes` | POST | Auto-detect axis lines |
| `/api/digitize` | POST | Extract data points |

## How It Works

1. **Upload**: Image is validated (max 10MB, max 4000x4000, PNG/JPG/WEBP) and normalized to RGB
2. **Axis Detection**: Hough line transform finds axis boundaries, optional OCR reads tick labels
3. **Calibration**: User adjusts fiducial handles and enters axis min/max values
4. **Digitization**: Hybrid method runs blob detection first, falls back to template matching for non-standard markers
5. **Export**: Points displayed as table and available as CSV

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, OpenCV, scikit-image, numpy, scipy
- **Frontend**: React 18, TypeScript, Vite
- **Deployment**: Docker (CPU only)

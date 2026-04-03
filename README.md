# FastAPI Backend Setup

## 1) Create and activate virtual environment

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2) Install dependencies
```bash
pip install -r requirements.txt
```

## 3) Run development server
```bash
uvicorn app.main:app --reload
```

Server: `http://127.0.0.1:8000`

- API docs (Swagger): `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Endpoints
- `GET /`
- `GET /health`

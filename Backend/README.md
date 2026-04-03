# AI-Powered Financial Fraud Detection Backend

A modular FastAPI backend connected to MongoDB Atlas using `pymongo`.

## Project Structure

```text
Backend/
  app/
    api/
      routes/
        fraud.py
    core/
      config.py
      database.py
    models/
      schemas.py
    services/
      anomaly_service.py
      decision_service.py
      explainability_service.py
      profile_service.py
      risk_service.py
    utils/
      serializer.py
    main.py
  .env
  .env.example
  requirements.txt
```

## Features Implemented

- User behavior profiling
- Anomaly detection
- Risk scoring engine
- Decision engine (`APPROVE`, `MFA`, `BLOCK`)
- Explainability reasons
- CORS enabled for all origins
- MongoDB collections initialization (`users`, `transactions`, `alerts`)

## API Endpoints

- `POST /transaction`
- `GET /user/{user_id}`
- `GET /transactions`
- `GET /alerts`
- `GET /stats`
- `GET /health`

## Risk Scoring Rules

Higher risk when:

- amount > user average
- new location
- new device
- unusual time

Current scoring weights:

- amount above average: +35
- new location: +20
- new device: +20
- unusual time: +15

Decision thresholds:

- risk > 80: `BLOCK`
- risk 50-80: `MFA`
- risk < 50: `APPROVE`

## Run Locally

### 1) Create virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Configure environment

Update `.env` with your MongoDB Atlas URI and DB name.

### 4) Start API (host `0.0.0.0`, port `8000`)

```powershell
python -m app.main
```

Alternative:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger docs: `http://localhost:8000/docs`

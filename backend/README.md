# Fraud Ops FastAPI Backend (MongoDB)

This backend implements your MongoDB-first schema with three core collections:
- `users`
- `devices`
- `transactions`

It includes:
- Embedded user context (`device_centroid`, `known_devices`, `recent_behavior_seq`)
- User identity fields (`name`, `email`, `phone_no`)
- User `transaction_ids` array
- Unified transaction ledger with `frontend_payload`, `backend_snapshot`, and `pipeline_results`
- Environment-based MongoDB config via `.env`

## Setup

1. Open terminal in this folder:

```bash
cd backend
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Update `.env` with your MongoDB URL:

```env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=fraud_ops
API_HOST=0.0.0.0
API_PORT=8000
```

4. Start server:

```bash
python main.py
```

5. Populate MongoDB with sample Indian users/devices/transactions:

```bash
python seed_data.py
```

## API

- `GET /api/health`
- `POST /api/users`
- `GET /api/users/{user_key}`
- `GET /api/users?q=&limit=`
- `GET /api/users/search?query=&limit=`
- `GET /api/user/{user_key}/profile`
- `POST /api/devices/register`
- `POST /api/transactions/process`
- `GET /api/transactions/live?limit=20`
- `GET /api/transactions/{transaction_id}`
- `GET /api/transactions/user/{user_key}?limit=20`
- `GET /api/dashboard/stats`
- `GET /api/dashboard/fraud-ring`

Swagger:
- `http://localhost:8000/docs`

## Notes

- Mongo indexes are auto-created on app startup.
- `recent_behavior_seq` is capped to the latest 50 events.
- Transaction processing simulates inference output so you can plug in your Python model pipeline later.

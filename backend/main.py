import os

import uvicorn

from app.config import settings


if __name__ == "__main__":
    # Hard safeguard: backend startup must never trigger sample seeding.
    os.environ.setdefault("ENABLE_SAMPLE_SEEDING", "0")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )

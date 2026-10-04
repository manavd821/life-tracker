import logging

from fastapi import FastAPI

from app.api.routes.webhooks import router as webhooks_router

logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])

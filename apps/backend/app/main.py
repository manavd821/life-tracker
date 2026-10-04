from fastapi import FastAPI

from app.core.config import DESCRIPTION, PROJECT_NAME, VERSION

app = FastAPI(
    title=PROJECT_NAME,
    description=DESCRIPTION,
    version=VERSION,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
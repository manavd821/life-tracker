import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.activity_labels import router as activity_labels_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.behaviors import router as behaviors_router
from app.api.routes.context_tags import router as context_tags_router
from app.api.routes.patterns import router as patterns_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.webhooks import router as webhooks_router
from app.core.errors import DomainError

logging.basicConfig(level=logging.INFO)

app = FastAPI()


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, **exc.details}},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(behaviors_router, prefix="/api")
app.include_router(activity_labels_router, prefix="/api")
app.include_router(context_tags_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(patterns_router, prefix="/api")
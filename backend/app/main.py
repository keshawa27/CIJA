from fastapi import APIRouter, FastAPI, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .routers import admin, auth, cases, dashboard, intake, tasks
from .security import limiter

dev = settings.env == "dev"
app = FastAPI(
    title="CIJA",
    # the API description is only published in development
    docs_url="/api/docs" if dev else None,
    openapi_url="/api/openapi.json" if dev else None,
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"  # responses hold personal information
    return response


api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok"}


for module in (intake, auth, cases, tasks, dashboard, admin):
    api.include_router(module.router)
app.include_router(api)

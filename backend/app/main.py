from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import applications, employers, pipeline, profile, resumes, runs
from app.core.config import Settings
from app.core.errors import AppError, BadRequest, Conflict, NotFound, ProviderError
from app.workers.scheduler import start_scheduler

_STATUS_CODES = {NotFound: 404, BadRequest: 400, Conflict: 409, ProviderError: 502}
_READ_METHODS = {"GET", "HEAD", "OPTIONS"}


async def _handle_app_error(_: Request, error: AppError) -> JSONResponse:
    status = next((c for t, c in _STATUS_CODES.items() if isinstance(error, t)), 500)
    return JSONResponse(status_code=status, content={"detail": str(error)})


def create_app(run_scheduler: bool = False) -> FastAPI:
    origins = Settings().cors_origins

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        scheduler = start_scheduler(Settings()) if run_scheduler else None
        try:
            yield
        finally:
            if scheduler:
                scheduler.shutdown(wait=False)

    app = FastAPI(title="NZ Job Autopilot", lifespan=lifespan)

    @app.middleware("http")
    async def block_other_websites(request: Request, call_next):
        # Browsers can send form posts to localhost from any site. Only the dashboard may write.
        origin = request.headers.get("origin")
        if request.method not in _READ_METHODS and origin and origin not in origins:
            return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_exception_handler(AppError, _handle_app_error)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(pipeline.router)
    app.include_router(applications.router)
    app.include_router(profile.router)
    app.include_router(employers.router)
    app.include_router(resumes.router)
    app.include_router(runs.router)
    return app


app = create_app(run_scheduler=True)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import applications, pipeline, runs
from app.core.config import Settings
from app.core.errors import AppError, Conflict, NotFound, ProviderError

_STATUS_CODES = {NotFound: 404, Conflict: 409, ProviderError: 502}


async def _handle_app_error(_: Request, error: AppError) -> JSONResponse:
    status = next((c for t, c in _STATUS_CODES.items() if isinstance(error, t)), 500)
    return JSONResponse(status_code=status, content={"detail": str(error)})


def create_app() -> FastAPI:
    app = FastAPI(title="NZ Job Autopilot")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=Settings().cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.add_exception_handler(AppError, _handle_app_error)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(pipeline.router)
    app.include_router(applications.router)
    app.include_router(runs.router)
    return app


app = create_app()

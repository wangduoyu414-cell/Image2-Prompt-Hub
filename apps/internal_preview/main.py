"""Loopback-only API for review-required fixed-commit case preview."""

from __future__ import annotations

import io
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .repository import InternalPreviewError, InternalPreviewRepository


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@lru_cache(maxsize=1)
def _repository_provider() -> InternalPreviewRepository:
    return InternalPreviewRepository.from_environment()


def create_app(
    *,
    repository: InternalPreviewRepository | None = None,
    enforce_loopback: bool = True,
) -> FastAPI:
    app = FastAPI(
        title="Image2 Internal Review-Required Preview",
        version="v1",
        description="Local-only preview of fixed-commit Prompt/image pairs before public rights approval.",
    )

    def get_repository() -> InternalPreviewRepository:
        return repository if repository is not None else _repository_provider()

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):  # type: ignore[no-untyped-def]
        client_host = request.client.host if request.client else None
        if enforce_loopback and client_host not in {"127.0.0.1", "::1"}:
            return _error(403, "preview_loopback_only", "The internal preview is available only from loopback.")
        response = await call_next(request)
        response.headers["X-Image2-Preview-Mode"] = "internal-review-required"
        return response

    @app.exception_handler(InternalPreviewError)
    async def preview_error(_: Request, error: InternalPreviewError) -> JSONResponse:
        status = 404 if error.error_code == "preview_asset_not_found" else 502 if "integrity" in error.error_code else 503
        return _error(status, error.error_code, str(error))

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
        return _error(500, "preview_internal_error", "The internal preview request could not be completed.")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "internal_review_required"}

    @app.get("/readyz")
    def readiness(preview: InternalPreviewRepository = Depends(get_repository)) -> dict[str, object]:
        return preview.status()

    @app.get("/api/internal-preview/v1/cases")
    def list_cases(
        q: Annotated[str | None, Query(max_length=512)] = None,
        source: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        page: Annotated[int, Query(ge=1, le=10_000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=48)] = 24,
        preview: InternalPreviewRepository = Depends(get_repository),
    ) -> dict[str, object]:
        return preview.list_cases(q=q, source=source, page=page, page_size=page_size)

    @app.get("/api/internal-preview/v1/assets/{asset_id}", response_model=None)
    def asset(
        asset_id: Annotated[str, Path(pattern="^[0-9a-f]{64}$")],
        preview: InternalPreviewRepository = Depends(get_repository),
    ) -> StreamingResponse:
        delivery = preview.read_asset(asset_id)
        return StreamingResponse(
            io.BytesIO(delivery.content),
            media_type=delivery.media_type,
            headers={
                "ETag": f'"{delivery.content_sha256}"',
                "Content-Length": str(len(delivery.content)),
                "Cache-Control": "private, no-store",
            },
        )

    return app


app = create_app()

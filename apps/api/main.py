"""FastAPI application for current immutable publication snapshots only."""

import io
from typing import Annotated

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from .assets import AssetIntegrityFailure, AssetStore, AssetStoreUnavailable, S3AssetStore
from .models import (
    CaseDetailResponse,
    CaseListResponse,
    ErrorResponse,
    HealthResponse,
    PublicationResponse,
    ReadinessResponse,
    V2CaseDetailResponse,
    V2CaseListResponse,
)
from .repository import (
    AssetNotAuthorized,
    CaseNotFound,
    ContentPublicationRepository,
    PublicReadRepository,
    PublicationSnapshotInvalid,
    PublicationUnavailable,
)
from .repository_v2 import ContentPublicationV2Repository, PublicationV2Reader, PublicReadRepositoryV2


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def _repository_provider() -> PublicReadRepository:
    return PublicReadRepository(ContentPublicationRepository.from_environment())


def _asset_store_provider() -> AssetStore:
    return S3AssetStore.from_environment()


def _repository_v2_provider() -> PublicReadRepositoryV2:
    return PublicReadRepositoryV2(ContentPublicationV2Repository.from_environment())


def create_app(
    *,
    repository: PublicReadRepository | None = None,
    repository_v2: PublicReadRepositoryV2 | None = None,
    asset_store: AssetStore | None = None,
) -> FastAPI:
    """Create a side-effect-free app; no DB/S3 connection occurs at startup."""

    app = FastAPI(
        title="Image2 Public Publication API",
        version="v1+v2",
        description="Read-only projections of the independent v1 and v2 immutable publication snapshots.",
    )

    def get_repository() -> PublicReadRepository:
        return repository if repository is not None else _repository_provider()

    def get_asset_store() -> AssetStore:
        return asset_store if asset_store is not None else _asset_store_provider()

    def get_repository_v2() -> PublicReadRepositoryV2:
        return repository_v2 if repository_v2 is not None else _repository_v2_provider()

    @app.exception_handler(PublicationUnavailable)
    async def publication_unavailable(_: Request, __: PublicationUnavailable) -> JSONResponse:
        return _error(503, "publication_unavailable", "The publication service is temporarily unavailable.")

    @app.exception_handler(PublicationSnapshotInvalid)
    async def publication_snapshot_invalid(_: Request, __: PublicationSnapshotInvalid) -> JSONResponse:
        return _error(503, "publication_unavailable", "The current publication cannot be safely served.")

    @app.exception_handler(AssetStoreUnavailable)
    async def asset_store_unavailable(_: Request, __: AssetStoreUnavailable) -> JSONResponse:
        return _error(503, "asset_unavailable", "The asset service is temporarily unavailable.")

    @app.exception_handler(AssetIntegrityFailure)
    async def asset_integrity_failure(_: Request, __: AssetIntegrityFailure) -> JSONResponse:
        return _error(502, "asset_integrity_failed", "The current asset did not pass integrity checks.")

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error(422, "invalid_request", "Request parameters are invalid.")

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
        return _error(500, "internal_error", "The request could not be completed.")

    @app.get("/healthz", response_model=HealthResponse, response_model_exclude_none=True)
    def health() -> dict[str, str]:
        """Process-only health check: it deliberately has no database dependency."""

        return {"status": "ok"}

    @app.get(
        "/readyz",
        response_model=ReadinessResponse,
        responses={503: {"model": ErrorResponse}},
    )
    def readiness(publications: PublicReadRepository = Depends(get_repository)) -> dict[str, str]:
        return {"status": "ready", "state": publications.readiness()}

    @app.get(
        "/api/v1/publication",
        response_model=PublicationResponse,
        responses={503: {"model": ErrorResponse}},
    )
    def publication(publications: PublicReadRepository = Depends(get_repository)) -> dict[str, object]:
        return publications.publication()

    @app.get(
        "/api/v1/cases",
        response_model=CaseListResponse,
        responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def list_cases(
        publications: Annotated[PublicReadRepository, Depends(get_repository)],
        q: Annotated[str | None, Query(max_length=256)] = None,
        source: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        display_policy: Annotated[str | None, Query(pattern="^(mirror_allowed|attribution_required|link_only)$")] = None,
        tag: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        has_reference: bool | None = None,
        page: Annotated[int, Query(ge=1, le=10_000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> dict[str, object]:
        return publications.list_cases(
            q=q,
            source=source,
            display_policy=display_policy,
            tag=tag,
            has_reference=has_reference,
            page=page,
            page_size=page_size,
        )

    @app.get(
        "/api/v2/publication",
        response_model=PublicationResponse,
        responses={503: {"model": ErrorResponse}},
    )
    def publication_v2(publications: PublicReadRepositoryV2 = Depends(get_repository_v2)) -> dict[str, object]:
        return publications.publication()

    @app.get(
        "/api/v2/cases",
        response_model=V2CaseListResponse,
        responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def list_cases_v2(
        publications: Annotated[PublicReadRepositoryV2, Depends(get_repository_v2)],
        q: Annotated[str | None, Query(max_length=256)] = None,
        source: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        display_policy: Annotated[str | None, Query(pattern="^(mirror_allowed|attribution_required|link_only)$")] = None,
        tag: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
        has_reference: bool | None = None,
        page: Annotated[int, Query(ge=1, le=10_000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> dict[str, object]:
        return publications.list_cases(
            q=q,
            source=source,
            display_policy=display_policy,
            tag=tag,
            has_reference=has_reference,
            page=page,
            page_size=page_size,
        )

    @app.get(
        "/api/v2/cases/{public_case_key}",
        response_model=V2CaseDetailResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def case_detail_v2(
        public_case_key: Annotated[str, Path(pattern="^[0-9a-f]{64}$")],
        publications: Annotated[PublicReadRepositoryV2, Depends(get_repository_v2)],
    ) -> dict[str, object]:
        try:
            return publications.case_detail(public_case_key)
        except CaseNotFound:
            return _error(404, "case_not_found", "The requested case is not in the current publication.")  # type: ignore[return-value]

    @app.get(
        "/api/v1/cases/{canonical_key}",
        response_model=CaseDetailResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def case_detail(
        canonical_key: Annotated[str, Path(min_length=1, max_length=128)],
        publications: Annotated[PublicReadRepository, Depends(get_repository)],
    ) -> dict[str, object]:
        try:
            return publications.case_detail(canonical_key)
        except CaseNotFound:
            return _error(404, "case_not_found", "The requested case is not in the current publication.")  # type: ignore[return-value]

    @app.get(
        "/api/v1/assets/{content_sha256}",
        response_model=None,
        responses={
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    def asset(
        content_sha256: Annotated[str, Path(pattern="^[0-9a-f]{64}$")],
        publications: Annotated[PublicReadRepository, Depends(get_repository)],
    ) -> StreamingResponse | JSONResponse:
        try:
            locator = publications.locate_current_asset(content_sha256)
        except AssetNotAuthorized:
            return _error(404, "asset_not_found", "The requested asset is not in the current mirrorable publication.")
        store = asset_store if asset_store is not None else get_asset_store()
        delivery = store.read(locator)
        return StreamingResponse(
            io.BytesIO(delivery.content),
            media_type=delivery.media_type,
            headers={
                "ETag": f'"{delivery.content_sha256}"',
                "Content-Length": str(len(delivery.content)),
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    @app.get(
        "/api/v2/assets/{content_sha256}",
        response_model=None,
        responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    def asset_v2(
        content_sha256: Annotated[str, Path(pattern="^[0-9a-f]{64}$")],
        publications: Annotated[PublicReadRepositoryV2, Depends(get_repository_v2)],
    ) -> StreamingResponse | JSONResponse:
        try:
            locator = publications.locate_current_asset(content_sha256)
        except AssetNotAuthorized:
            return _error(404, "asset_not_found", "The requested asset is not in the current mirrorable publication.")
        store = asset_store if asset_store is not None else get_asset_store()
        delivery = store.read(locator)
        return StreamingResponse(
            io.BytesIO(delivery.content),
            media_type=delivery.media_type,
            headers={
                "ETag": f'"{delivery.content_sha256}"',
                "Content-Length": str(len(delivery.content)),
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    return app


app = create_app()

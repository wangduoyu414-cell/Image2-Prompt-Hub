"""Authenticated HTTP boundary for explicit case-level human review."""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated, Any, Literal, Protocol

from fastapi import Depends, FastAPI, Header, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps.api.assets import (
    AssetIntegrityFailure,
    AssetStore,
    AssetStoreSettings,
    AssetStoreUnavailable,
    S3AssetStore,
)
from content.review import OutputReviewDecision, ReviewSubmission

from .auth import (
    AdminAuthError,
    AdminAuthService,
    AdminAuthSettings,
    AdminPrincipal,
    SESSION_COOKIE,
)
from .repository import AdminRepositoryError, AdminReviewRepository
from apps.observability import configure_observability


class AdminRepository(Protocol):
    def readiness(self) -> str: ...
    def list_queue(self, *, state: str | None, limit: int, offset: int) -> dict[str, Any]: ...
    def inspect_subject(self, source_case_version_id: int) -> dict[str, Any]: ...
    def submit_review(self, submission: ReviewSubmission) -> dict[str, Any]: ...
    def inspect_batch(self, batch_id: int) -> dict[str, Any]: ...
    def preview_candidate(self, source_case_version_id: int) -> dict[str, Any]: ...
    def locate_output(self, generation_output_id: int): ...
    def publication_v2_status(self) -> dict[str, Any]: ...
    def build_publication_v2(self, *, actor: str, idempotency_key: str) -> dict[str, Any]: ...
    def activate_publication_v2(self, version_id: int) -> dict[str, Any]: ...
    def rollback_publication_v2(self, version_id: int) -> dict[str, Any]: ...
    def record_takedown_v2(self, **facts: Any) -> dict[str, Any]: ...
    def operations_status(self) -> dict[str, Any]: ...


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class OutputDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_output_id: int = Field(gt=0)
    asset_rights: Literal["approved", "unknown", "internal_only", "blocked"]
    display_policy: Literal["mirror_allowed", "attribution_required", "link_only", "internal_only", "blocked"]
    public_display_role: Literal["public_primary", "public_gallery", "hidden"]
    decision_note: str = Field(min_length=1, max_length=2000)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_case_version_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_latest_batch_id: int | None = Field(default=None, gt=0)
    repository_license: str = Field(min_length=1, max_length=500)
    prompt_rights: Literal["approved", "unknown", "internal_only", "blocked"]
    author: str = Field(min_length=1, max_length=500)
    original_url: str = Field(min_length=1, max_length=2000)
    evidence_url: str = Field(min_length=1, max_length=2000)
    output_decisions: list[OutputDecisionRequest] = Field(min_length=1, max_length=100)
    review_note: str = Field(min_length=1, max_length=5000)


class BuildPublicationV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)


class VersionActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publication_version_v2_id: int = Field(gt=0)


class TakedownV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)
    scope_type: Literal["asset", "prompt", "case", "source"]
    scope_key: str = Field(min_length=1, max_length=1000)
    action: Literal["remove", "restore"]
    reason_code: str = Field(min_length=1, max_length=200)
    evidence_url: str = Field(min_length=1, max_length=2000)
    note: str = Field(min_length=1, max_length=5000)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@lru_cache(maxsize=1)
def _auth_provider() -> AdminAuthService:
    return AdminAuthService(AdminAuthSettings.from_environment())


@lru_cache(maxsize=1)
def _repository_provider() -> AdminReviewRepository:
    return AdminReviewRepository.from_environment()


@lru_cache(maxsize=1)
def _asset_store_provider() -> AssetStore:
    endpoint = os.environ.get("INVENTORY_S3_ENDPOINT_URL", "")
    access_key = os.environ.get("INVENTORY_S3_ACCESS_KEY", "")
    secret_key = os.environ.get("INVENTORY_S3_SECRET_KEY", "")
    return S3AssetStore(
        AssetStoreSettings(
            endpoint_url=endpoint,
            access_key_id=access_key,
            secret_access_key=secret_key,
            region_name=os.environ.get("INVENTORY_S3_REGION", "us-east-1"),
        )
    )


def _session_document(principal: AdminPrincipal) -> dict[str, Any]:
    return {
        "authenticated": True,
        "user": {"username": principal.username, "role": principal.role},
        "csrf_token": principal.csrf_token,
        "expires_at": principal.expires_at,
    }


def create_app(
    *,
    auth_service: AdminAuthService | None = None,
    repository: AdminRepository | None = None,
    asset_store: AssetStore | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Image2 Review Administration API",
        version="v1",
        description="Authenticated, explicit, case-level review administration without automatic publication.",
    )

    def get_auth() -> AdminAuthService:
        return auth_service if auth_service is not None else _auth_provider()

    def get_repository() -> AdminRepository:
        return repository if repository is not None else _repository_provider()

    def get_asset_store() -> AssetStore:
        return asset_store if asset_store is not None else _asset_store_provider()

    def get_principal(
        request: Request,
        auth: AdminAuthService = Depends(get_auth),
    ) -> AdminPrincipal:
        return auth.verify_session(request.cookies.get(SESSION_COOKIE))

    def get_reviewer(
        request: Request,
        principal: AdminPrincipal = Depends(get_principal),
        auth: AdminAuthService = Depends(get_auth),
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> AdminPrincipal:
        auth.assert_origin(request.headers.get("origin"))
        auth.assert_csrf(principal, csrf_token)
        auth.assert_role(principal, "reviewer", "admin")
        return principal

    def get_admin(
        request: Request,
        principal: AdminPrincipal = Depends(get_principal),
        auth: AdminAuthService = Depends(get_auth),
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> AdminPrincipal:
        auth.assert_origin(request.headers.get("origin"))
        auth.assert_csrf(principal, csrf_token)
        auth.assert_role(principal, "admin")
        return principal

    @app.middleware("http")
    async def admin_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(AdminAuthError)
    async def auth_error(_: Request, error: AdminAuthError) -> JSONResponse:
        if error.error_code == "admin_login_rate_limited":
            return _error(429, error.error_code, str(error))
        if error.error_code in {"admin_session_required", "admin_session_invalid", "admin_credentials_invalid"}:
            return _error(401, error.error_code, str(error))
        if error.error_code == "admin_auth_config_invalid":
            return _error(503, error.error_code, "Admin authentication is not configured.")
        return _error(403, error.error_code, str(error))

    @app.exception_handler(AdminRepositoryError)
    async def repository_error(_: Request, error: AdminRepositoryError) -> JSONResponse:
        if error.error_code in {"rights_review_v2_target_missing", "rights_review_v2_batch_missing", "admin_asset_not_found"}:
            return _error(404, error.error_code, str(error))
        if error.error_code in {
            "rights_review_v2_stale", "rights_review_v2_idempotency_conflict",
            "publication_v2_idempotency_conflict", "publication_v2_public_loss",
            "publication_v2_active_takedown", "publication_v2_stale_review", "publication_v2_stale_revision",
        }:
            return _error(409, error.error_code, str(error))
        if error.error_code in {"admin_database_unavailable", "content_schema_not_migrated", "operations_database_unavailable", "operations_schema_not_migrated", "operations_read_failed"}:
            return _error(503, error.error_code, "Review administration is temporarily unavailable.")
        return _error(422, error.error_code, str(error))

    @app.exception_handler(AssetStoreUnavailable)
    async def asset_unavailable(_: Request, __: AssetStoreUnavailable) -> JSONResponse:
        return _error(503, "admin_asset_unavailable", "Review asset storage is temporarily unavailable.")

    @app.exception_handler(AssetIntegrityFailure)
    async def asset_integrity(_: Request, __: AssetIntegrityFailure) -> JSONResponse:
        return _error(502, "admin_asset_integrity_failed", "Review asset integrity validation failed.")

    @app.exception_handler(RequestValidationError)
    async def request_invalid(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error(422, "admin_request_invalid", "Admin request data is invalid.")

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
        return _error(500, "admin_internal_error", "The admin request could not be completed.")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readiness(admin: AdminRepository = Depends(get_repository)) -> dict[str, str]:
        return {"status": "ready", "state": admin.readiness()}

    @app.post("/api/admin/v1/session/login")
    def login(
        body: LoginRequest,
        request: Request,
        auth: AdminAuthService = Depends(get_auth),
    ) -> JSONResponse:
        auth.assert_origin(request.headers.get("origin"))
        client_id = request.client.host if request.client else "unknown"
        user = auth.authenticate_credentials(body.username, body.password, client_id=client_id)
        token, principal = auth.issue_session(user)
        response = JSONResponse(content=_session_document(principal))
        response.set_cookie(
            key=SESSION_COOKIE,
            value=token,
            max_age=auth.settings.session_ttl_seconds,
            httponly=True,
            secure=auth.settings.secure_cookies,
            samesite="strict",
            path="/",
        )
        return response

    @app.get("/api/admin/v1/session")
    def session(principal: AdminPrincipal = Depends(get_principal)) -> dict[str, Any]:
        return _session_document(principal)

    @app.post("/api/admin/v1/session/logout")
    def logout(
        request: Request,
        principal: AdminPrincipal = Depends(get_principal),
        auth: AdminAuthService = Depends(get_auth),
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> JSONResponse:
        auth.assert_origin(request.headers.get("origin"))
        auth.assert_csrf(principal, csrf_token)
        response = JSONResponse(content={"status": "logged_out"})
        response.delete_cookie(SESSION_COOKIE, path="/", secure=auth.settings.secure_cookies, samesite="strict")
        return response

    @app.get("/api/admin/v1/review-queue")
    def review_queue(
        state: Annotated[str | None, Query(pattern="^(pending|review_required|publishable|internal_only|blocked)$")] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
        _: AdminPrincipal = Depends(get_principal),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.list_queue(state=state, limit=limit, offset=offset)

    @app.get("/api/admin/v1/operations")
    def operations(
        _: AdminPrincipal = Depends(get_principal),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.operations_status()

    @app.get("/api/admin/v1/review-subjects/{source_case_version_id}")
    def review_subject(
        source_case_version_id: Annotated[int, Path(gt=0)],
        _: AdminPrincipal = Depends(get_principal),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.inspect_subject(source_case_version_id)

    @app.get("/api/admin/v1/review-batches/{batch_id}")
    def review_batch(
        batch_id: Annotated[int, Path(gt=0)],
        _: AdminPrincipal = Depends(get_principal),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.inspect_batch(batch_id)

    @app.get("/api/admin/v1/review-subjects/{source_case_version_id}/candidate")
    def candidate_preview(
        source_case_version_id: Annotated[int, Path(gt=0)],
        _: AdminPrincipal = Depends(get_principal),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.preview_candidate(source_case_version_id)

    @app.get("/api/admin/v1/review-assets/{generation_output_id}", response_model=None)
    def review_asset(
        generation_output_id: Annotated[int, Path(gt=0)],
        _: AdminPrincipal = Depends(get_principal),
        admin: AdminRepository = Depends(get_repository),
        store: AssetStore = Depends(get_asset_store),
    ) -> StreamingResponse:
        delivery = store.read(admin.locate_output(generation_output_id))
        return StreamingResponse(
            io.BytesIO(delivery.content),
            media_type=delivery.media_type,
            headers={
                "ETag": f'"{delivery.content_sha256}"',
                "Content-Length": str(len(delivery.content)),
                "Cache-Control": "private, no-store",
            },
        )

    @app.post("/api/admin/v1/reviews")
    def submit_review(
        body: ReviewRequest,
        principal: AdminPrincipal = Depends(get_reviewer),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        submission = ReviewSubmission(
            source_case_version_id=body.source_case_version_id,
            idempotency_key=body.idempotency_key,
            expected_latest_batch_id=body.expected_latest_batch_id,
            repository_license=body.repository_license,
            prompt_rights=body.prompt_rights,
            author=body.author,
            original_url=body.original_url,
            evidence_url=body.evidence_url,
            reviewer=principal.username,
            reviewed_at=datetime.now(timezone.utc),
            output_decisions=tuple(
                OutputReviewDecision(
                    generation_output_id=item.generation_output_id,
                    asset_rights=item.asset_rights,
                    display_policy=item.display_policy,
                    public_display_role=item.public_display_role,
                    decision_note=item.decision_note,
                )
                for item in body.output_decisions
            ),
            review_note=body.review_note,
        )
        result = admin.submit_review(submission)
        return {**result, "authenticated_reviewer": principal.username}

    @app.get("/api/admin/v1/publication-v2")
    def publication_v2_status(
        _: AdminPrincipal = Depends(get_principal),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.publication_v2_status()

    @app.post("/api/admin/v1/publication-v2/build")
    def build_publication_v2(
        body: BuildPublicationV2Request,
        principal: AdminPrincipal = Depends(get_admin),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.build_publication_v2(actor=principal.username, idempotency_key=body.idempotency_key)

    @app.post("/api/admin/v1/publication-v2/activate")
    def activate_publication_v2(
        body: VersionActionRequest,
        _: AdminPrincipal = Depends(get_admin),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.activate_publication_v2(body.publication_version_v2_id)

    @app.post("/api/admin/v1/publication-v2/rollback")
    def rollback_publication_v2(
        body: VersionActionRequest,
        _: AdminPrincipal = Depends(get_admin),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.rollback_publication_v2(body.publication_version_v2_id)

    @app.post("/api/admin/v1/takedowns-v2")
    def record_takedown_v2(
        body: TakedownV2Request,
        principal: AdminPrincipal = Depends(get_admin),
        admin: AdminRepository = Depends(get_repository),
    ) -> dict[str, Any]:
        return admin.record_takedown_v2(
            idempotency_key=body.idempotency_key,
            scope_type=body.scope_type,
            scope_key=body.scope_key,
            action=body.action,
            reason_code=body.reason_code,
            evidence_url=body.evidence_url,
            note=body.note,
            requested_by=principal.username,
            requested_at=datetime.now(timezone.utc),
        )

    configure_observability("image2-admin-api", app=app)
    return app


app = create_app()

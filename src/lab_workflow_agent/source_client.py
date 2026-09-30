"""Narrow, application-owned reads from the local Lab Storage API."""

import re
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import AppError, SourceSettings
from .source_models import (ErrorResponse, LocationRead, MaterialRead, MaterialSearchArgs,
                            Page, PageArgs, UserRead)

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class SourceError(AppError):
    def __init__(self, message: str, *, status: int | None = None,
                 code: str | None = None, request_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id


class LabStorageClient:
    def __init__(self, settings: SourceSettings, *, transport: httpx.BaseTransport | None = None):
        # Revalidate even if application code modified a settings object.
        settings = SourceSettings.model_validate(settings.model_dump())
        if not settings.token_present:
            raise AppError("Lab Storage bearer token is required.")
        self._token = settings.bearer_token
        self.last_request_id: str | None = None
        self._client = httpx.Client(
            base_url=settings.api_url,
            headers={"Authorization": "Bearer " + self._token.get_secret_value()},
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=transport if transport is not None else httpx.HTTPTransport(retries=0),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LabStorageClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _safe_metadata(self, value: object) -> str | None:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
            return None
        if self._token.get_secret_value() in value:
            return None
        return value

    def get_material(self, material_id: int) -> MaterialRead:
        self.last_request_id = None
        # bool is an int subclass, so isinstance alone would accept True.
        if type(material_id) is not int or material_id <= 0:
            raise AppError("Material ID must be a positive integer.")
        material = self._get(f"/materials/{material_id}", MaterialRead, "material")
        if material.id != material_id:
            raise SourceError("Lab Storage returned a different material ID.", status=200,
                              request_id=self.last_request_id)
        return material

    def current_user(self) -> UserRead:
        return self._get("/users/me", UserRead, "user")

    def get_location(self, location_id: int) -> LocationRead:
        self.last_request_id = None
        if type(location_id) is not int or location_id <= 0:
            raise AppError("Location ID must be a positive integer.")
        location = self._get(f"/locations/{location_id}", LocationRead, "location")
        if location.id != location_id:
            raise SourceError("Lab Storage returned a different location ID.", status=200,
                              request_id=self.last_request_id)
        return location

    def search_materials(self, **filters: object) -> Page[MaterialRead]:
        self.last_request_id = None
        try:
            args = MaterialSearchArgs.model_validate(filters)
        except ValidationError:
            raise AppError("Invalid material search arguments.") from None
        result = self._get("/materials/search", Page[MaterialRead], "material page",
                           params=args.model_dump(exclude_none=True))
        self._check_page(result, args)
        if not args.include_archived and any(item.is_archived for item in result.items):
            raise SourceError("Lab Storage returned unexpected archived materials.", status=200,
                              request_id=self.last_request_id)
        return result

    def list_locations(self, *, page: int = 1, size: int = 10) -> Page[LocationRead]:
        self.last_request_id = None
        try:
            args = PageArgs(page=page, size=size)
        except ValidationError:
            raise AppError("Invalid location pagination arguments.") from None
        result = self._get("/locations", Page[LocationRead], "location page", params=args.model_dump())
        self._check_page(result, args)
        return result

    def _check_page(self, result: Page, args: PageArgs) -> None:
        if result.page != args.page or result.size != args.size:
            raise SourceError("Lab Storage returned unexpected pagination.", status=200,
                              request_id=self.last_request_id)

    def _get(self, path: str, model: type[ResponseT], label: str,
             *, params: dict | None = None) -> ResponseT:
        # Only the five application-owned read methods supply paths to this helper.
        self.last_request_id = None
        try:
            response = self._client.get(path, params=params)
        except httpx.TimeoutException:
            raise SourceError("Lab Storage request timed out. No retry was attempted.") from None
        except httpx.HTTPError:
            raise SourceError("Lab Storage request failed. No retry was attempted.") from None

        self.last_request_id = self._safe_metadata(response.headers.get("X-Request-ID"))
        if response.status_code != 200:
            code = None
            try:
                envelope = ErrorResponse.model_validate(response.json())
                code = self._safe_metadata(envelope.error.code)
            except (ValueError, UnicodeError):
                pass
            messages = {
                401: "Lab Storage authentication failed.",
                403: "Lab Storage access denied.",
                404: "Lab Storage record or route was not found.",
                422: "Lab Storage rejected the request parameters.",
            }
            message = messages.get(response.status_code, "Lab Storage returned an unsuccessful response.")
            if response.status_code == 404 and code == "MATERIAL_NOT_FOUND":
                message = "Material was not found."
            raise SourceError(message, status=response.status_code, code=code,
                              request_id=self.last_request_id)
        try:
            return model.model_validate(response.json())
        except (ValueError, UnicodeError, ValidationError):
            raise SourceError(f"Lab Storage returned invalid {label} data.", status=200,
                              request_id=self.last_request_id) from None

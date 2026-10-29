from types import MappingProxyType
from typing import Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from litellm.integrations.otel.model.config import (
    ExporterOwner,
    ExporterSpec,
    OpenTelemetryV2Config,
)
from litellm.integrations.otel.presets.utils import ensure_mappers
from litellm.types.utils import StandardCallbackDynamicParams

FUTUREAGI_DEFAULT_BASE_URL: Final = "https://api.futureagi.com"
FUTUREAGI_TRACES_PATH: Final = "/tracer/v1/traces"
FUTUREAGI_DEFAULT_PROJECT: Final = "litellm"
FUTUREAGI_API_KEY_HEADER: Final = "X-Api-Key"
FUTUREAGI_SECRET_KEY_HEADER: Final = "X-Secret-Key"


class _FutureAGISettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore", frozen=True)

    api_key: str | None = Field(default=None, validation_alias="FI_API_KEY")
    secret_key: str | None = Field(default=None, validation_alias="FI_SECRET_KEY")
    base_url: str | None = Field(default=None, validation_alias="FI_BASE_URL")
    project_name: str | None = Field(default=None, validation_alias="FI_PROJECT_NAME")


def _headers(api_key: str | None, secret_key: str | None) -> str | None:
    if not (api_key and secret_key):
        return None
    return f"{FUTUREAGI_API_KEY_HEADER}={api_key},{FUTUREAGI_SECRET_KEY_HEADER}={secret_key}"


def futureagi_preset(
    *,
    config_overrides: OpenTelemetryV2Config | None = None,
    allow_missing_credentials: bool = False,
) -> OpenTelemetryV2Config:
    settings: Final = _FutureAGISettings()
    base: Final = config_overrides or OpenTelemetryV2Config()
    base_url: Final = (settings.base_url or FUTUREAGI_DEFAULT_BASE_URL).rstrip("/")
    spec: Final = ExporterSpec(
        kind="otlp_http",
        traces_endpoint=f"{base_url}{FUTUREAGI_TRACES_PATH}",
        headers=_headers(settings.api_key, settings.secret_key),
        owner=ExporterOwner.FUTUREAGI,
        requires_headers=True,
    )
    return base.model_copy(
        update=MappingProxyType(
            {
                "exporters": (*base.exporters, spec),
                "mapper_names": ensure_mappers(base.mapper_names, "genai"),
                "resource_attributes": {
                    **base.resource_attributes,
                    "project_name": settings.project_name or FUTUREAGI_DEFAULT_PROJECT,
                    "project_type": "observe",
                },
            }
        )
    )


def futureagi_dynamic_headers(
    params: StandardCallbackDynamicParams,
) -> dict[str, str]:  # mutable-ok: DYNAMIC_HEADERS_BY_CALLBACK returns a dict
    api_key: Final = params.get("futureagi_api_key")
    secret_key: Final = params.get("futureagi_secret_key")
    if not (api_key and secret_key):
        return {}
    return {
        FUTUREAGI_API_KEY_HEADER: api_key,
        FUTUREAGI_SECRET_KEY_HEADER: secret_key,
    }

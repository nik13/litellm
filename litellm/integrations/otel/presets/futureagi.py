"""Future AGI preset — OTLP/HTTP exporter to Future AGI + GenAI vocabulary."""

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

#: Future AGI serves OTLP/HTTP traces on this path rather than the bare ``/v1/traces``.
FUTUREAGI_TRACES_PATH: Final = "/tracer/v1/traces"

#: Future AGI files every export under the project its ``project_name`` resource
#: attribute names, and rejects a batch that names none, so this is the project
#: when ``FI_PROJECT_NAME`` is unset. A name that does not exist yet is created.
FUTUREAGI_DEFAULT_PROJECT: Final = "litellm"

FUTUREAGI_API_KEY_HEADER: Final = "X-Api-Key"
FUTUREAGI_SECRET_KEY_HEADER: Final = "X-Secret-Key"


class _FutureAGISettings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore", frozen=True)

    # The env vars the Future AGI SDKs read, so one set of variables configures both.
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
    return base.model_copy(
        update={
            "exporters": [
                *base.exporters,
                ExporterSpec(
                    kind="otlp_http",
                    # A full URL: the plumbing would otherwise append ``/v1/traces``.
                    traces_endpoint=f"{base_url}{FUTUREAGI_TRACES_PATH}",
                    # Both keys or neither: one key alone only earns a 401 per batch.
                    headers=_headers(settings.api_key, settings.secret_key),
                    owner=ExporterOwner.FUTUREAGI,
                    # Without the operator's keys only key/team traffic, which brings its
                    # own, is exported.
                    requires_headers=True,
                ),
            ],
            # Future AGI reads the OTel GenAI semantic conventions natively.
            "mapper_names": ensure_mappers(base.mapper_names, "genai"),
            "resource_attributes": {
                **base.resource_attributes,
                "project_name": settings.project_name or FUTUREAGI_DEFAULT_PROJECT,
                # Turns ``user.id`` on the spans into a Future AGI end user.
                "project_type": "observe",
            },
        }
    )


def futureagi_dynamic_headers(
    params: StandardCallbackDynamicParams,
) -> dict[str, str]:  # mutable-ok: DYNAMIC_HEADERS_BY_CALLBACK returns a dict
    """Per-request Future AGI OTLP headers from team/key dynamic params.

    A key pair belongs to one Future AGI workspace, so a team with its own pair gets its
    traces in its own workspace, under the operator's ``FI_PROJECT_NAME``.
    """
    api_key: Final = params.get("futureagi_api_key")
    secret_key: Final = params.get("futureagi_secret_key")
    if not (api_key and secret_key):
        return {}
    return {
        FUTUREAGI_API_KEY_HEADER: api_key,
        FUTUREAGI_SECRET_KEY_HEADER: secret_key,
    }

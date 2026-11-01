import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    keycloak_healthcheck_url: str | None
    synapse_healthcheck_url: str | None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_client_id: str = "console"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            database_url=os.getenv("ADMINAPI_DATABASE_URL"),
            keycloak_healthcheck_url=os.getenv("KEYCLOAK_HEALTHCHECK_URL"),
            synapse_healthcheck_url=os.getenv("SYNAPSE_HEALTHCHECK_URL"),
            oidc_issuer=os.getenv("OIDC_ISSUER"),
            oidc_audience=os.getenv("OIDC_AUDIENCE"),
            oidc_jwks_url=os.getenv("OIDC_JWKS_URL"),
            oidc_client_id=os.getenv("OIDC_CLIENT_ID", "console"),
        )

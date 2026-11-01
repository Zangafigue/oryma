import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    keycloak_healthcheck_url: str | None
    synapse_healthcheck_url: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            database_url=os.getenv("ADMINAPI_DATABASE_URL"),
            keycloak_healthcheck_url=os.getenv("KEYCLOAK_HEALTHCHECK_URL"),
            synapse_healthcheck_url=os.getenv("SYNAPSE_HEALTHCHECK_URL"),
        )

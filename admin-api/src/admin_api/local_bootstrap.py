import argparse
import asyncio
import json
import os
from uuid import UUID

import asyncpg

MINISTRY_CODE = "DEV-DEMO"
MINISTRY_NAME = "Ministère fictif de démonstration"
BOOTSTRAP_LOCK_ID = 734_201_107


class LocalBootstrapConflict(Exception):
    pass


async def bootstrap_local_admin(
    database_url: str,
    keycloak_id: UUID,
    matrix_id: str,
    admin_name: str,
) -> bool:
    connection = await asyncpg.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "SELECT pg_advisory_xact_lock($1)",
                BOOTSTRAP_LOCK_ID,
            )
            existing = await connection.fetchrow(
                """
                SELECT a.keycloak_id, a.matrix_id, a.nom_complet, a.role::text AS role,
                       a.statut::text AS statut, m.code AS ministere_code,
                       m.nom AS ministere_nom
                FROM agents AS a
                LEFT JOIN ministeres AS m ON m.id = a.ministere_id
                WHERE a.keycloak_id = $1
                """,
                keycloak_id,
            )
            if existing is not None:
                matches = (
                    existing["matrix_id"] == matrix_id
                    and existing["nom_complet"] == admin_name
                    and existing["role"] == "admin"
                    and existing["statut"] == "actif"
                    and existing["ministere_code"] == MINISTRY_CODE
                    and existing["ministere_nom"] == MINISTRY_NAME
                )
                if matches:
                    return False
                raise LocalBootstrapConflict(
                    "Cet identifiant Keycloak est déjà lié à un autre compte agent."
                )

            matrix_exists = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM agents WHERE matrix_id = $1)",
                matrix_id,
            )
            if matrix_exists:
                raise LocalBootstrapConflict(
                    "Cet identifiant Matrix est déjà lié à un autre compte agent."
                )

            active_admin_exists = await connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM agents WHERE role = 'admin' AND statut = 'actif'
                )
                """
            )
            if active_admin_exists:
                raise LocalBootstrapConflict(
                    "Un administrateur actif existe déjà ; le bootstrap initial est refusé."
                )

            ministry_id = await connection.fetchval(
                "SELECT id FROM ministeres WHERE code = $1",
                MINISTRY_CODE,
            )
            if ministry_id is None:
                ministry_id = await connection.fetchval(
                    """
                    INSERT INTO ministeres (code, nom)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    MINISTRY_CODE,
                    MINISTRY_NAME,
                )
            else:
                ministry_name = await connection.fetchval(
                    "SELECT nom FROM ministeres WHERE id = $1",
                    ministry_id,
                )
                if ministry_name != MINISTRY_NAME:
                    raise LocalBootstrapConflict(
                        f"Le code ministère {MINISTRY_CODE} existe avec un autre nom."
                    )

            agent_id = await connection.fetchval(
                """
                INSERT INTO agents
                    (keycloak_id, matrix_id, nom_complet, ministere_id, fonction, role)
                VALUES ($1, $2, $3, $4, 'Administrateur initial (développement)', 'admin')
                RETURNING id
                """,
                keycloak_id,
                matrix_id,
                admin_name,
                ministry_id,
            )
            await connection.execute(
                """
                INSERT INTO audit_log (acteur_id, action, cible_id, details)
                VALUES (NULL, 'BOOTSTRAP_ADMIN_LOCAL', $1, $2::jsonb)
                """,
                agent_id,
                json.dumps(
                    {
                        "ministere_code": MINISTRY_CODE,
                        "keycloak_id": str(keycloak_id),
                    }
                ),
            )
        return True
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crée le premier administrateur fictif pour un environnement local."
    )
    parser.add_argument("--confirm-local", action="store_true", required=True)
    parser.add_argument("--keycloak-id", required=True, type=UUID)
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--admin-name", required=True)
    args = parser.parse_args()

    if os.getenv("ORYMA_ENVIRONMENT", "production").strip().lower() != "development":
        raise SystemExit(
            "Bootstrap refusé : ORYMA_ENVIRONMENT doit valoir development pour cette commande."
        )
    if os.getenv("ORYMA_ENABLE_LOCAL_BOOTSTRAP", "").strip().lower() != "true":
        raise SystemExit(
            "Bootstrap refusé : définissez ORYMA_ENABLE_LOCAL_BOOTSTRAP=true "
            "uniquement dans votre environnement local de développement."
        )
    database_url = os.getenv("ADMINAPI_DATABASE_URL")
    if not database_url:
        raise SystemExit("ADMINAPI_DATABASE_URL doit être défini.")

    try:
        created = asyncio.run(
            bootstrap_local_admin(
                database_url,
                args.keycloak_id,
                args.matrix_id,
                args.admin_name,
            )
        )
    except LocalBootstrapConflict as error:
        raise SystemExit(str(error)) from error

    if created:
        print("Ministère fictif et administrateur local créés.")
    else:
        print("Bootstrap déjà effectué ; aucune modification.")


if __name__ == "__main__":
    main()

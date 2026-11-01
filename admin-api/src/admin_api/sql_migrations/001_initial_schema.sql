CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE role_agent AS ENUM ('admin', 'agent');
CREATE TYPE statut_agent AS ENUM ('actif', 'revoque');

CREATE TABLE ministeres (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    nom TEXT NOT NULL
);

CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keycloak_id UUID UNIQUE NOT NULL,
    matrix_id TEXT UNIQUE NOT NULL,
    nom_complet TEXT NOT NULL,
    ministere_id INTEGER REFERENCES ministeres(id),
    fonction TEXT,
    role role_agent NOT NULL DEFAULT 'agent',
    statut statut_agent NOT NULL DEFAULT 'actif',
    cree_le TIMESTAMPTZ NOT NULL DEFAULT now(),
    cree_par UUID REFERENCES agents(id),
    revoque_le TIMESTAMPTZ,
    revoque_par UUID REFERENCES agents(id)
);

CREATE TABLE niveaux_classification (
    code TEXT PRIMARY KEY,
    libelle TEXT NOT NULL,
    duree_vie_secondes INTEGER NOT NULL,
    transfert_interdit BOOLEAN NOT NULL DEFAULT false
);

INSERT INTO niveaux_classification (code, libelle, duree_vie_secondes)
VALUES
    ('DIFFUSION_RESTREINTE', 'Diffusion restreinte', 604800),
    ('CONFIDENTIEL', 'Confidentiel', 86400);

CREATE TABLE salles (
    room_id TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    niveau TEXT REFERENCES niveaux_classification(code),
    cree_par UUID REFERENCES agents(id),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    acteur_id UUID REFERENCES agents(id),
    action TEXT NOT NULL,
    cible_id UUID REFERENCES agents(id),
    details JSONB,
    horodatage TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX agents_statut_idx ON agents (statut);
CREATE INDEX audit_log_horodatage_idx ON audit_log (horodatage DESC);

CREATE FUNCTION prevent_audit_log_mutation() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_log est en ajout seul';
END;
$$;

CREATE TRIGGER audit_log_append_only
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();

CREATE TRIGGER audit_log_no_truncate
BEFORE TRUNCATE ON audit_log
FOR EACH STATEMENT EXECUTE FUNCTION prevent_audit_log_mutation();

CREATE TABLE agent_revocations (
    agent_id UUID PRIMARY KEY REFERENCES agents(id),
    acteur_id UUID NOT NULL REFERENCES agents(id),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT now(),
    mis_a_jour_le TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_revocation_steps (
    agent_id UUID NOT NULL REFERENCES agent_revocations(agent_id) ON DELETE CASCADE,
    ordre SMALLINT NOT NULL CHECK (ordre BETWEEN 1 AND 6),
    terminee_le TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_id, ordre)
);

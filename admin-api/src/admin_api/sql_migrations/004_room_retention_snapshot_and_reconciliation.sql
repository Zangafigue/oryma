ALTER TABLE salles
    ADD COLUMN duree_vie_secondes INTEGER;

UPDATE salles AS salle
SET duree_vie_secondes = niveau.duree_vie_secondes
FROM niveaux_classification AS niveau
WHERE salle.niveau = niveau.code;

ALTER TABLE salles
    ADD CONSTRAINT salles_retention_snapshot_consistency
    CHECK (
        (niveau IS NULL AND duree_vie_secondes IS NULL)
        OR (
            niveau IS NOT NULL
            AND duree_vie_secondes IS NOT NULL
            AND duree_vie_secondes > 0
        )
    );

CREATE TABLE reconciliation_salles (
    room_id TEXT PRIMARY KEY,
    statut TEXT NOT NULL DEFAULT 'A_RECONCILIER'
        CHECK (statut IN ('A_RECONCILIER', 'RESOLUE')),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolu_le TIMESTAMPTZ,
    CHECK (
        (statut = 'A_RECONCILIER' AND resolu_le IS NULL)
        OR (statut = 'RESOLUE' AND resolu_le IS NOT NULL)
    )
);

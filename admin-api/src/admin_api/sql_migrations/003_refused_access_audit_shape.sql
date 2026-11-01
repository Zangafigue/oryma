ALTER TABLE audit_log
    ADD CONSTRAINT audit_log_refused_access_details_shape
    CHECK (
        action <> 'TENTATIVE_ACCES_REFUSE'
        OR (
            details IS NOT NULL
            AND jsonb_typeof(details) = 'object'
            AND details ?& ARRAY['route', 'motif']
            AND details - 'route' - 'motif' = '{}'::jsonb
            AND jsonb_typeof(details->'route') = 'string'
            AND details->>'route' LIKE '/api/v1/%'
            AND details->>'motif' = 'ROLE_INSUFFISANT'
        )
    );

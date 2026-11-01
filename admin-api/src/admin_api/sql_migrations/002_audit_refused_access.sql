ALTER TABLE audit_log
    ADD CONSTRAINT audit_log_details_no_credentials_or_ip
    CHECK (
        details IS NULL
        OR NOT (
            details ?| ARRAY[
                'ip', 'adresse_ip', 'token', 'access_token', 'refresh_token',
                'authorization', 'session', 'session_id'
            ]
        )
    );

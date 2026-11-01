FROM quay.io/keycloak/keycloak:26.8.1

COPY realm-export.json.template /oryma/realm-export.json.template
COPY docker-entrypoint.sh /oryma/docker-entrypoint.sh

ENTRYPOINT ["/oryma/docker-entrypoint.sh"]

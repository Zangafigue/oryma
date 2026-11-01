#!/bin/sh
set -eu

mkdir -p /opt/keycloak/data/import
sed \
  -e "s|__ORYMA_HOST__|$ORYMA_HOST|g" \
  -e "s|__OIDC_SYNAPSE_SECRET__|$OIDC_SYNAPSE_SECRET|g" \
  -e "s|__ADMIN_API_OIDC_SECRET__|$ADMIN_API_OIDC_SECRET|g" \
  /oryma/realm-export.json.template > /opt/keycloak/data/import/oryma-realm.json

exec /opt/keycloak/bin/kc.sh "$@"

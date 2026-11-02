#!/bin/sh
set -eu

ORYMA_CADDY_CA=/caddy/caddy/pki/authorities/local/root.crt

if [ ! -r "$ORYMA_CADDY_CA" ]; then
  echo "La CA interne de Caddy est introuvable : démarrez Caddy avant Synapse." >&2
  exit 1
fi

install -m 644 "$ORYMA_CADDY_CA" /usr/local/share/ca-certificates/oryma-caddy.crt
update-ca-certificates >/dev/null
# Le processus Synapse n'a pas accès au fichier Caddy monté en mode 0600.
# Il doit donc utiliser la copie publique de la CA pour ses appels OIDC HTTPS.
export SSL_CERT_FILE=/usr/local/share/ca-certificates/oryma-caddy.crt

if [ ! -f /data/.oryma-config-ready ]; then
  /start.py generate

  case "$ORYMA_HOST" in
    *[!a-z0-9.-]* | '')
      echo 'ORYMA_HOST doit contenir uniquement des minuscules, chiffres, points ou tirets.' >&2
      exit 64
      ;;
  esac

  sed \
    -e "s|__ORYMA_HOST__|$ORYMA_HOST|g" \
    -e "s|__SYNAPSE_DB_PASSWORD__|$SYNAPSE_DB_PASSWORD|g" \
    -e "s|__SYNAPSE_REGISTRATION_SECRET__|$SYNAPSE_REGISTRATION_SECRET|g" \
    -e "s|__SYNAPSE_MACAROON_SECRET__|$SYNAPSE_MACAROON_SECRET|g" \
    -e "s|__SYNAPSE_FORM_SECRET__|$SYNAPSE_FORM_SECRET|g" \
    -e "s|__OIDC_SYNAPSE_SECRET__|$OIDC_SYNAPSE_SECRET|g" \
    /oryma/homeserver.yaml.template > /data/homeserver.yaml

  touch /data/.oryma-config-ready
fi

# Conserver les endpoints OIDC HTTPS canoniques si le fichier a été généré
# avant une correction de configuration.
sed -i \
  -e "s|^    token_endpoint: .*|    token_endpoint: \"https://${ORYMA_HOST}/auth/realms/oryma/protocol/openid-connect/token\"|" \
  -e "s|^    jwks_uri: .*|    jwks_uri: \"https://${ORYMA_HOST}/auth/realms/oryma/protocol/openid-connect/certs\"|" \
  /data/homeserver.yaml

exec /start.py run

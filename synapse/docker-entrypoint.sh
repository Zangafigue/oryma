#!/bin/sh
set -eu

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
    /oryma/homeserver.yaml.template > /data/homeserver.yaml

  touch /data/.oryma-config-ready
fi

exec /start.py run

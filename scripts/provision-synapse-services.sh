#!/bin/sh
# Crée les deux comptes techniques locaux Synapse et garde leurs jetons hors Git.
set -eu

oryma_env_file="${1:-.env}"

if [ ! -f "$oryma_env_file" ]; then
  echo "Fichier d'environnement introuvable : $oryma_env_file" >&2
  exit 1
fi

oryma_host="$(sed -n 's/^ORYMA_HOST=//p' "$oryma_env_file" | tail -n 1)"
case "$oryma_host" in
  ''|*[!A-Za-z0-9._:-]*)
    echo "ORYMA_HOST est absent ou invalide dans $oryma_env_file." >&2
    exit 1
    ;;
esac

if grep -qE '^SYNAPSE_ADMIN_ACCESS_TOKEN=.' "$oryma_env_file" || \
  grep -qE '^SYNAPSE_ROOM_SERVICE_ACCESS_TOKEN=.' "$oryma_env_file"; then
  echo "Des jetons de service Synapse existent déjà ; aucun remplacement n'est effectué." >&2
  exit 1
fi

oryma_existing_users="$({
  docker compose --env-file "$oryma_env_file" exec -T postgres \
    psql -U postgres -d synapse -tAc \
    "SELECT name FROM users WHERE name IN ('@oryma-admin-service:${oryma_host}', '@oryma-room-service:${oryma_host}');"
} | tr -d '[:space:]')"

if [ -n "$oryma_existing_users" ]; then
  echo "Un compte technique Synapse existe déjà ; aucun remplacement n'est effectué." >&2
  exit 1
fi

oryma_provision_token() {
  oryma_localpart="$1"
  oryma_admin_flag="$2"

  docker compose --env-file "$oryma_env_file" exec -T synapse \
    python3 - "$oryma_localpart" "$oryma_admin_flag" <<'PY'
import hashlib
import hmac
import json
import secrets
import sys
import urllib.request

import yaml

username, admin_flag = sys.argv[1:]
config = yaml.safe_load(open("/data/homeserver.yaml", encoding="utf-8"))
secret = config["registration_shared_secret"]
password = secrets.token_urlsafe(32)
endpoint = "http://127.0.0.1:8008/_synapse/admin/v1/register"

with urllib.request.urlopen(endpoint, timeout=10) as response:
    nonce = json.load(response)["nonce"]

admin = admin_flag == "true"
parts = [nonce, username, password, "admin" if admin else "notadmin"]
mac = hmac.new(secret.encode(), "\x00".join(parts).encode(), hashlib.sha1).hexdigest()
payload = json.dumps(
    {"nonce": nonce, "username": username, "password": password, "admin": admin, "mac": mac}
).encode()
request = urllib.request.Request(
    endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"
)
with urllib.request.urlopen(request, timeout=10) as response:
    print(json.load(response)["access_token"], end="")
PY
}

umask 077
oryma_admin_token="$(oryma_provision_token oryma-admin-service true)"
oryma_room_token="$(oryma_provision_token oryma-room-service false)"
oryma_tmp_file="$(mktemp "${oryma_env_file}.XXXXXX")"
trap 'rm -f "$oryma_tmp_file"' EXIT

grep -v -E '^(SYNAPSE_ADMIN_ACCESS_TOKEN|SYNAPSE_ROOM_SERVICE_MATRIX_ID|SYNAPSE_ROOM_SERVICE_ACCESS_TOKEN)=' \
  "$oryma_env_file" > "$oryma_tmp_file" || true
printf '\nSYNAPSE_ADMIN_ACCESS_TOKEN=%s\n' "$oryma_admin_token" >> "$oryma_tmp_file"
printf 'SYNAPSE_ROOM_SERVICE_MATRIX_ID=@oryma-room-service:%s\n' "$oryma_host" >> "$oryma_tmp_file"
printf 'SYNAPSE_ROOM_SERVICE_ACCESS_TOKEN=%s\n' "$oryma_room_token" >> "$oryma_tmp_file"
chmod 600 "$oryma_tmp_file"
mv "$oryma_tmp_file" "$oryma_env_file"
trap - EXIT

echo "Comptes techniques Synapse créés ; les jetons sont stockés uniquement dans $oryma_env_file."

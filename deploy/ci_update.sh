#!/usr/bin/env bash
# Deploy remoto disparado pelo GitHub Actions via SSH autenticado.
# Preserva banco, curriculo, secrets e virtualenv. Faz rollback se a versao falhar.
set -Eeuo pipefail

if (( EUID != 0 )); then
  echo "ERROR: execute com sudo -n (root na VM)" >&2
  exit 1
fi
archive="${1:-}"
revision="${2:-}"
if [[ ! "$revision" =~ ^[a-f0-9]{40}$ ]] ||
   [[ "$archive" != "/tmp/dev-find-ci-${revision}.tgz" ]]; then
  echo "ERROR: arquivo/revisao do deploy invalidos" >&2
  exit 1
fi

app=/opt/dev-find
envfile=/etc/dev-find.env
state=/var/lib/dev-find
private=/opt/dev-find-private
backup_dir=/var/backups/dev-find
service=dev-find.service

for file in "$archive" "$envfile" "$app/pyproject.toml" "$app/.venv/bin/python"; do
  if [[ ! -f "$file" ]]; then
    echo "ERROR: instalacao incompleta ou arquivo ausente: $file" >&2
    exit 1
  fi
done
if ! systemctl cat "$service" >/dev/null 2>&1; then
  echo "ERROR: servico $service nao instalado" >&2
  exit 1
fi
install -d -m 0700 "$backup_dir"
stage="$(mktemp -d /tmp/devfind-stage.XXXXXXXX)"
backup="$backup_dir/deploy-${revision}-$(date -u +%Y%m%dT%H%M%SZ).tgz"
applied=0
success=0

cleanup() {
  code=$?
  trap - EXIT
  if (( success == 0 && applied == 1 )); then
    echo "Deploy falhou. Restaurando arquivos da versao anterior..." >&2
    tar -xzf "$backup" -C "$app" || true
    "$app/.venv/bin/python" -m pip install -q -e "$app" || true
    systemctl daemon-reload || true
    systemctl restart "$service" || true
    echo "Rollback executado; verifique os logs do servico." >&2
  fi
  rm -rf -- "$stage"
  rm -f -- "$archive"
  exit "$code"
}
trap cleanup EXIT

tar -xzf "$archive" -C "$stage"
test -f "$stage/pyproject.toml"
test -f "$stage/src/dev_find/app.py"
test -f "$stage/deploy/ci_update.sh"

# Apenas codigo e artefatos publicos entram no backup. Dados privados ficam
# fora do checkout ou explicitamente excluidos.
tar -C "$app" --exclude='./.venv' --exclude='./data' --exclude='./.env' \
  --exclude='./.git' --exclude='./*.db' --exclude='./*.db-wal' --exclude='./*.db-shm' \
  -czf "$backup" .

systemctl stop "$service"
applied=1
cp -a "$stage/." "$app/"
"$app/.venv/bin/python" -m pip install -q -e "$app"
"$app/.venv/bin/python" -m compileall -q "$app/src"
runuser -u devfind -- "$app/.venv/bin/python" -c \
  "import dev_find, dev_find.cli, dev_find.app, dev_find.registry, dev_find.receita_sync"
systemctl daemon-reload
systemctl restart "$service"

# Confirmar que o processo sobrevive ao startup; sucesso sem restart e proibido.
for i in 1 2 3 4 5 6; do
  sleep 2
  if ! systemctl is-active --quiet "$service"; then
    echo "ERROR: servico ficou inativo apos o deploy" >&2
    exit 1
  fi
done

install -d -o devfind -g devfind -m 0750 "$state"
printf '%s\n' "$revision" > "$state/deployed-sha"
chown devfind:devfind "$state/deployed-sha"
chmod 0640 "$state/deployed-sha"
success=1
echo "DEPLOY_OK: $revision"

#!/usr/bin/env bash
# migrate.sh — aplica migrations pendentes e registra na tabela schema_migrations.
#
# Uso:
#   bash database/migrate.sh               # aplica tudo que falta
#   bash database/migrate.sh --status      # só lista o status, não aplica nada
#
# Requer docker compose rodando com o container "postgres".

set -euo pipefail

COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
DB_USER="rpg_user"
DB_NAME="rpg_platform"
MIGRATIONS_DIR="$(dirname "$0")/migrations"
POSTGRES_SVC="postgres"

STATUS_ONLY=false
[[ "${1:-}" == "--status" ]] && STATUS_ONLY=true

# ── helpers ───────────────────────────────────────────────────────────────────

psql_cmd() {
    docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SVC" \
        psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "$1"
}

psql_file() {
    docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SVC" \
        psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$1"
}

GREEN='\033[32m' YELLOW='\033[33m' RED='\033[31m' BOLD='\033[1m' RESET='\033[0m'

ok()   { echo -e "${GREEN}✅  $*${RESET}"; }
skip() { echo -e "${YELLOW}⏭   $*${RESET}"; }
err()  { echo -e "${RED}❌  $*${RESET}"; }
info() { echo -e "${BOLD}$*${RESET}"; }

# ── garante que a tabela de controle existe ───────────────────────────────────

psql_cmd "
CREATE TABLE IF NOT EXISTS schema_migrations (
    id          SERIAL PRIMARY KEY,
    migration   VARCHAR(255) NOT NULL UNIQUE,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
" > /dev/null

# ── lista migrations já aplicadas ────────────────────────────────────────────

applied=$(psql_cmd "SELECT migration FROM schema_migrations ORDER BY migration;")

# ── itera sobre os arquivos .sql em ordem ────────────────────────────────────

info "\n🔍 Verificando migrations em: $MIGRATIONS_DIR"
echo "──────────────────────────────────────────────────────────"

pending=0
applied_now=0
errors=0

for sql_file in "$MIGRATIONS_DIR"/*.sql; do
    filename=$(basename "$sql_file")

    # Verifica se já foi aplicada
    if echo "$applied" | grep -qx "$filename"; then
        skip "$filename — já aplicada"
        continue
    fi

    pending=$((pending + 1))

    if $STATUS_ONLY; then
        echo -e "   ${YELLOW}📌 PENDENTE${RESET}  $filename"
        continue
    fi

    echo -n "   Aplicando $filename ... "

    # Copia o arquivo para dentro do container e executa
    docker compose -f "$COMPOSE_FILE" cp "$sql_file" "${POSTGRES_SVC}:/tmp/${filename}" 2>/dev/null

    if docker compose -f "$COMPOSE_FILE" exec -T "$POSTGRES_SVC" \
        psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
             -f "/tmp/${filename}" > /dev/null 2>&1; then

        # Registra na tabela de controle
        psql_cmd "INSERT INTO schema_migrations (migration) VALUES ('${filename}') ON CONFLICT DO NOTHING;" > /dev/null
        applied_now=$((applied_now + 1))
        ok "OK"

    else
        errors=$((errors + 1))
        err "FALHOU — abortando"
        exit 1
    fi
done

echo "──────────────────────────────────────────────────────────"

if $STATUS_ONLY; then
    total=$(echo "$applied" | grep -c . || true)
    echo -e "\n${BOLD}Status:${RESET} ${total} aplicadas, ${pending} pendentes"
else
    if [[ $applied_now -gt 0 ]]; then
        ok "${applied_now} migration(s) aplicada(s) com sucesso."
    elif [[ $pending -eq 0 ]]; then
        ok "Banco já está atualizado — nenhuma migration pendente."
    fi
fi

# ── exibe histórico completo ──────────────────────────────────────────────────

echo -e "\n${BOLD}📋 Histórico completo:${RESET}"
echo "──────────────────────────────────────────────────────────"
psql_cmd "SELECT migration, to_char(applied_at AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI:SS') AS applied_at FROM schema_migrations ORDER BY migration;" \
    | column -t -s '|' 2>/dev/null || \
  psql_cmd "SELECT migration, applied_at FROM schema_migrations ORDER BY migration;"
echo "──────────────────────────────────────────────────────────"

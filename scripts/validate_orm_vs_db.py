#!/usr/bin/env python3
"""
Hook PostToolUse do Claude Code — valida ORM models vs banco de dados.

Ativado automaticamente quando qualquer orm_models.py é editado (Edit/Write).
Compara as colunas declaradas no ORM com as colunas reais do PostgreSQL.

Saída:
  ✅  Tabelas com colunas 100% corretas
  ❌  Lista de divergências por tabela:
        + coluna_no_orm_mas_nao_no_banco  (migration pendente)
        - coluna_no_banco_mas_nao_no_orm  (coluna órfã / faltando no ORM)
  ⚠️   Tabela não existe no banco        (migration nunca rodou)

Exit code:
  0  — tudo OK (ou arquivo não é orm_models.py)
  1  — divergências encontradas
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

# ─── Configuração do projeto ──────────────────────────────────────────────────

# Detecta PROJECT_ROOT subindo a partir da localização deste script
_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _SCRIPT_DIR.parent           # RPG-IA/
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"

DB_USER     = "rpg_user"
DB_NAME     = "rpg_platform"
POSTGRES_SVC = "postgres"

# ─── Parser AST ───────────────────────────────────────────────────────────────


def _func_name(call: ast.Call) -> str:
    """Extrai o nome da função de uma chamada AST."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _first_string_arg(call: ast.Call) -> str | None:
    """
    Retorna o primeiro argumento posicional SE for uma string literal.
    Usado para detectar nome explícito de coluna:
      mapped_column("class", String(100)) → "class"
    """
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def extract_orm_tables(file_path: str) -> dict[str, dict]:
    """
    Lê um arquivo orm_models.py e retorna:
      {
        "table_name": {
          "class":   "ClassName",
          "columns": {"col1", "col2", ...},   # nomes reais no banco
        },
        ...
      }

    Regras de mapeamento ORM → nome da coluna no banco:
      - mapped_column("col_name", ...)  → "col_name"  (nome explícito)
      - mapped_column(Type, ...)        → attr_name    (mesmo nome do atributo Python)
      - relationship(...)               → ignorado     (não é coluna)
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"⚠️  Não foi possível ler o arquivo: {exc}", file=sys.stderr)
        return {}

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        print(f"⚠️  Erro de sintaxe em {Path(file_path).name}: {exc}", file=sys.stderr)
        return {}

    tables: dict[str, dict] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        table_name: str | None = None
        columns: set[str] = set()

        for item in node.body:
            # ── __tablename__ = "..." ──────────────────────────────────────
            if (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and item.targets[0].id == "__tablename__"
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            ):
                table_name = item.value.value
                continue

            # ── attr: Mapped[X] = <call>(...) ──────────────────────────────
            if not (isinstance(item, ast.AnnAssign) and item.value and isinstance(item.value, ast.Call)):
                continue

            call = item.value
            fname = _func_name(call)

            # Só nos importa mapped_column; relationship e outros são ignorados
            if fname != "mapped_column":
                continue

            # Nome do atributo Python
            if not isinstance(item.target, ast.Name):
                continue
            attr_name: str = item.target.id

            # Nome real da coluna no banco
            explicit = _first_string_arg(call)
            db_col = explicit if explicit is not None else attr_name

            columns.add(db_col)

        if table_name:
            tables[table_name] = {"class": node.name, "columns": columns}

    return tables


# ─── Consulta ao PostgreSQL ───────────────────────────────────────────────────


def _run_docker_query(sql: str) -> subprocess.CompletedProcess | None:
    """Executa uma query SQL no container postgres via docker compose exec."""
    try:
        return subprocess.run(
            [
                "docker", "compose",
                "-f", str(COMPOSE_FILE),
                "exec", "-T", POSTGRES_SVC,
                "psql", "-U", DB_USER, "-d", DB_NAME,
                "-t", "-A",        # saída limpa: sem cabeçalho, alinhado
                "-c", sql,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(PROJECT_ROOT),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_db_columns(table_name: str) -> set[str] | None:
    """
    Retorna o conjunto de colunas de uma tabela no banco.
    Retorna None  →  tabela não existe OU banco inacessível.
    Retorna set() →  tabela existe mas sem colunas (improvável).
    """
    sql = (
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name='{table_name}' "
        "ORDER BY ordinal_position;"
    )
    result = _run_docker_query(sql)

    if result is None or result.returncode != 0:
        return None     # docker / postgres inacessível

    cols = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    # Tabela não existe = query retorna 0 linhas
    return cols if cols else None


def db_is_accessible() -> bool:
    """Verifica rapidamente se o banco está acessível."""
    result = _run_docker_query("SELECT 1;")
    return result is not None and result.returncode == 0


# ─── Relatório ────────────────────────────────────────────────────────────────

_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


def _ok(msg: str) -> str:
    return f"{_GREEN}✅  {msg}{_RESET}"


def _err(msg: str) -> str:
    return f"{_RED}❌  {msg}{_RESET}"


def _warn(msg: str) -> str:
    return f"{_YELLOW}⚠️   {msg}{_RESET}"


def _info(msg: str) -> str:
    return f"{_CYAN}ℹ️  {msg}{_RESET}"


def compare_and_report(file_path: str) -> int:
    """
    Compara ORM models com o banco para todas as tabelas do arquivo.
    Retorna 0 se tudo OK, 1 se houver divergências.
    """
    tables = extract_orm_tables(file_path)
    if not tables:
        print(_info(f"Nenhuma tabela ORM detectada em: {Path(file_path).name}"))
        return 0

    # Tenta verificar conectividade do banco
    if not db_is_accessible():
        print(_warn("PostgreSQL não acessível — containers rodando? Skipping validação."))
        return 0

    try:
        rel_path = Path(file_path).relative_to(PROJECT_ROOT)
    except ValueError:
        rel_path = Path(file_path)

    print(f"\n{_BOLD}🔍 Validando ORM vs banco — {rel_path}{_RESET}")
    print("─" * 65)

    has_errors = False

    for table_name, info in sorted(tables.items()):
        orm_cols: set[str] = info["columns"]
        class_name: str    = info["class"]
        db_cols            = get_db_columns(table_name)

        # ── Tabela não existe no banco ──────────────────────────────────────
        if db_cols is None:
            print(_warn(
                f"{class_name} → tabela '{table_name}' NÃO EXISTE no banco\n"
                f"       Execute a migration para criar a tabela."
            ))
            has_errors = True
            continue

        only_in_orm = orm_cols - db_cols
        only_in_db  = db_cols  - orm_cols

        # ── Tudo certo ──────────────────────────────────────────────────────
        if not only_in_orm and not only_in_db:
            print(_ok(
                f"{class_name} → '{table_name}' "
                f"({len(orm_cols)} col{'s' if len(orm_cols) != 1 else ''} — OK)"
            ))
            continue

        # ── Divergências ────────────────────────────────────────────────────
        has_errors = True
        print(_err(f"{class_name} → '{table_name}'"))

        if only_in_orm:
            print(f"     {_YELLOW}📌 No ORM mas NÃO no banco (migration pendente?):{_RESET}")
            for col in sorted(only_in_orm):
                print(f"        {_GREEN}+{_RESET} {col}")

        if only_in_db:
            print(f"     {_YELLOW}🗑️  No banco mas NÃO no ORM (órfã / faltando no ORM):{_RESET}")
            for col in sorted(only_in_db):
                print(f"        {_RED}-{_RESET} {col}")

        print()

    print("─" * 65)
    if has_errors:
        print(_err("Divergências encontradas. Verifique as migrations."))
    else:
        print(_ok("Todos os ORM models batem com o banco de dados."))
    print()

    return 1 if has_errors else 0


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> int:
    # Lê o JSON enviado pelo Claude Code via stdin
    try:
        raw = sys.stdin.read()
        hook_data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        hook_data = {}

    # file_path vem dentro de tool_input (Edit ou Write)
    tool_input = hook_data.get("tool_input", {})
    file_path  = tool_input.get("file_path", "")

    # Só age em orm_models.py
    if "orm_models" not in Path(file_path).name:
        return 0

    if not os.path.isfile(file_path):
        print(_warn(f"Arquivo não encontrado: {file_path}"))
        return 0

    return compare_and_report(file_path)


if __name__ == "__main__":
    sys.exit(main())

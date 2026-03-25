# Migrations (Alembic)

As migrations são gerenciadas pelo Alembic, configurado no serviço `gateway`.

## Comandos

```bash
# Criar nova migration
docker compose exec gateway alembic revision --autogenerate -m "descricao"

# Aplicar migrations
docker compose exec gateway alembic upgrade head

# Reverter última migration
docker compose exec gateway alembic downgrade -1

# Ver histórico
docker compose exec gateway alembic history
```

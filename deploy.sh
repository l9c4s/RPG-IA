#!/bin/bash
# Deploy script — VPS Ubuntu 22.04 LTS
set -euo pipefail

echo "🚀 RPG-IA Deploy"

# Verificar .env
if [ ! -f .env ]; then
  echo "❌ .env não encontrado. Copie .env.template para .env e preencha as variáveis."
  exit 1
fi

# Verificar dependências
for cmd in docker docker-compose; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "❌ $cmd não encontrado. Instale antes de continuar."
    exit 1
  fi
done

# SSL — gerar certificado se domínio configurado
source .env
if [ -n "${DOMAIN:-}" ] && [ "$DOMAIN" != "yourdomain.com" ]; then
  if [ ! -f nginx/ssl/fullchain.pem ]; then
    echo "📜 Obtendo certificado SSL para $DOMAIN..."
    docker run --rm \
      -v "$(pwd)/nginx/ssl:/etc/letsencrypt/live/$DOMAIN" \
      -p 80:80 \
      certbot/certbot certonly --standalone \
      --non-interactive --agree-tos \
      --email "admin@$DOMAIN" \
      -d "$DOMAIN"
  fi
fi

# Pull e build
echo "🔨 Buildando imagens..."
docker compose build --parallel

# Subir infra primeiro
echo "🗄️  Subindo infraestrutura (postgres, redis, minio)..."
docker compose up -d postgres redis minio
echo "⏳ Aguardando serviços de infraestrutura..."
sleep 10

# Migrations
echo "🔄 Rodando migrations..."
docker compose run --rm gateway alembic upgrade head 2>/dev/null || true

# Subir todos os serviços
echo "🟢 Subindo todos os serviços..."
docker compose up -d

# Status
echo ""
echo "✅ Deploy concluído!"
docker compose ps

echo ""
echo "📊 URLs:"
echo "  Frontend:       http://${DOMAIN:-localhost}"
echo "  API Gateway:    http://${DOMAIN:-localhost}/api"
echo "  Celery Flower:  http://${DOMAIN:-localhost}:5555"
echo "  MinIO Console:  http://${DOMAIN:-localhost}:9001"

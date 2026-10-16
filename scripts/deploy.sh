#!/usr/bin/env bash
# Деплой на сервере: берёт готовый образ из реестра (артефакт сборки) и перезапускает стек.
# Нужен файл .env с CLICKER_IMAGE (см. .env.example).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Нет файла .env. Скопируйте .env.example в .env и заполните." >&2
  exit 1
fi

git pull --ff-only || true
docker compose pull clicker
docker compose up -d --no-build
docker image prune -f

# Проверка после деплоя
for i in $(seq 1 15); do
  if curl -fsS http://localhost:5000/health >/dev/null; then
    echo "Деплой успешен: /health отвечает."
    exit 0
  fi
  sleep 2
done
echo "Приложение не отвечает после деплоя." >&2
docker compose logs --tail=50 clicker
exit 1

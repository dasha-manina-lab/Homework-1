#!/usr/bin/env bash
# Запуск всего стека из исходников (для преподавателя).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up --build -d
echo "Приложение:  http://localhost:5000"
echo "Health:      http://localhost:5000/health"
echo "Метрики:     http://localhost:5000/metrics"
echo "Prometheus:  http://localhost:9090"
echo "Grafana:     http://localhost:3000  (дашборд 'Student Clicker')"

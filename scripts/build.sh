#!/usr/bin/env bash
# Локальная сборка образа и быстрая проверка.
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -t student-clicker:local .
echo "Образ student-clicker:local собран."

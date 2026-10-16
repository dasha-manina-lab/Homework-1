#!/usr/bin/env bash
# Один раз на новом Ubuntu-сервере: ставит Docker и клонирует репозиторий.
# Использование: ./server-setup.sh https://github.com/ЛОГИН/student-clicker.git
set -euo pipefail
REPO="${1:?Укажите URL репозитория}"
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
git clone "$REPO" ~/student-clicker
cp ~/student-clicker/.env.example ~/student-clicker/.env
echo "Отредактируйте ~/student-clicker/.env, перелогиньтесь и запустите scripts/deploy.sh"

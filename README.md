# Student Clicker: контейнер, CI/CD и мониторинг

Кликер про студента, который проходит путь от абитуриента до кандидата докторской. Приложение простое. Главное здесь процесс: сборка, артефакт, деплой и метрики.

## Ссылки для проверки

Приложение работает в GitHub Codespaces. Ссылки действуют, пока Codespace запущен.

| Что | Ссылка |
|---|---|
| Приложение (интерфейс) | `https://organic-space-cod-wrjwgrqpvjgv2vg-5000.app.github.dev/` |
| Health check | `https://organic-space-abc123-5000.app.github.dev/health` |
| Метрики приложения | `https://organic-space-abc123-5000.app.github.dev/metrics` |
| Grafana (дашборд «Student Clicker») | `https://organic-space-cod-wrjwgrqpvjgv2vg-3000.app.github.dev/` |
| Prometheus | `https://organic-space-cod-wrjwgrqpvjgv2vg-9090.app.github.dev/` |

Grafana открывается без входа, в режиме просмотра. Вход администратора: `admin` / `password`.

## Быстрый запуск из исходников

Нужны Docker и Docker Compose.

```bash
git clone https://github.com/dasha-manina-lab/Homework-1.git
cd Homework-1
docker compose up --build
```

Вместо этого можно запустить `./bash.sh` или `./scripts/run.sh`.

После запуска откройте:

| Что | Адрес |
|---|---|
| Приложение | http://localhost:5000 |
| Health check | http://localhost:5000/health |
| Метрики | http://localhost:5000/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (дашборд «Student Clicker») |

### Запуск в GitHub Codespaces

В Codespaces не работает сеть между контейнерами: они не видят друг друга по именам. Поэтому там используется дополнительный файл, который запускает контейнеры в сети хоста:

```bash
docker compose -f docker-compose.yml -f docker-compose.codespaces.yml up -d --build
```

На обычном компьютере или сервере достаточно основной команды `docker compose up --build`.

## Состав проекта

| Файл | Назначение |
|---|---|
| `app.py` | Приложение (Flask) и метрики |
| `Dockerfile` | Описание контейнера |
| `docker-compose.yml` | Приложение, Prometheus, Grafana, cAdvisor, node-exporter |
| `docker-compose.codespaces.yml` | Добавка для запуска в Codespaces (сеть хоста) |
| `prometheus.yml` | Что и как часто собирает Prometheus |
| `prometheus.codespaces.yml` | То же для Codespaces (адреса через `localhost`) |
| `grafana/` | Источник данных и готовый дашборд, подхватываются автоматически |
| `scripts/build.sh` | Скрипт сборки образа |
| `scripts/deploy.sh` | Скрипт деплоя на сервере |
| `scripts/run.sh`, `bash.sh` | Запуск стека из исходников |
| `scripts/server-setup.sh` | Разовая подготовка сервера |
| `.github/workflows/ci-cd.yml` | Пайплайн GitHub Actions |
| `.gitlab-ci.yml` | Тот же пайплайн для GitLab |

## Приложение

- Клик по студенту даёт XP. Накопленный XP повышает уровень (от абитуриента до PhD).
- В магазине можно купить улучшения: кофе и ноутбук дают XP в секунду, учебник усиливает клик.
- Прогресс сохраняется в файл `/data/state.json` в томе `clicker_data`. Он переживает перезапуск контейнера.
- Приложение запускается через gunicorn с одним воркером: состояние игры хранится в памяти процесса.

## CI/CD: как это работает

1. **Исходники** лежат в git. Разработчик делает `git push` в ветку `main`.
2. **Сборка и проверка (CI).** Пайплайн ставит зависимости и запускает smoke-тест: `/health`, главная страница, клик, наличие метрик.
3. **Артефакт.** Пайплайн собирает Docker-образ и сохраняет его в реестре GitHub (GHCR) с двумя тегами: `latest` и хэш коммита. Хэш позволяет откатиться на любую версию. Образ виден в разделе Packages репозитория.
4. **Деплой (CD).** Пайплайн заходит на сервер по SSH и запускает `scripts/deploy.sh`.
5. **На сервере.** `deploy.sh` скачивает новый образ из реестра, перезапускает контейнеры и проверяет `/health`. Если приложение не отвечает, скрипт завершается с ошибкой и показывает логи.
6. **Сохранение.** Данные лежат в Docker-томах: прогресс игры (`clicker_data`), метрики (`prom_data`), настройки Grafana (`grafana_data`). После деплоя и перезапуска они не теряются.

Изменить приложение просто: правим код, делаем push, пайплайн собирает новую версию образа.

### Состояние деплоя

Выделенного сервера для проекта нет, поэтому шаг деплоя по умолчанию выключен: job `deploy` пропускается (статус skipped), а `build` проходит полностью. Приложение и мониторинг показываются в Codespaces.

Скрипты деплоя готовы. Чтобы включить шаг деплоя на сервере, нужно:

1. Выполнить на сервере `scripts/server-setup.sh`, заполнить `.env` (см. `.env.example`).
2. Добавить секреты репозитория: `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`.
3. Создать переменную репозитория `DEPLOY_ENABLED` со значением `true`.

## Метрики

| Требование | Где смотреть |
|---|---|
| Health check | `/health`; `HEALTHCHECK` в Dockerfile (`docker ps` показывает `healthy`); панель Health в Grafana (метрика `up`) |
| Посещений в час | `increase(student_page_visits_total[1h])`; считает только заходы на главную страницу |
| Ресурсы потребляемые | CPU и память приложения (метрики процесса `process_cpu_seconds_total`, `process_resident_memory_bytes`); данные контейнера из cAdvisor, когда он их отдаёт |
| Ресурсы доступные | Память и диск хоста: доступно и всего (node-exporter) |
| Использование приложения | Клики, уровни, XP, запросы по endpoint, латентность |

Служебные запросы `/metrics` и `/health` в счётчик запросов не попадают.

## Структура сервисов

| Сервис | Порт | Назначение |
|---|---|---|
| `clicker` | 5000 | Приложение и метрики |
| `prometheus` | 9090 | Сбор и хранение метрик |
| `grafana` | 3000 | Дашборд |
| `cadvisor` | 8080 (в Codespaces 8081) | Метрики контейнеров |
| `node-exporter` | 9100 | Метрики хоста |

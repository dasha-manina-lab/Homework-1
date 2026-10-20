# Student Clicker: контейнер, CI/CD и мониторинг

Кликер про студента, который проходит путь от абитуриента до кандидата докторской. Приложение простое. Главное здесь процесс: сборка, артефакт, деплой и метрики.

## Ссылки для проверки

| Что | Ссылка |
|---|---|
| Приложение (интерфейс) | https://student-clicker.onrender.com |
| Health check | https://student-clicker.onrender.com/health |
| Метрики приложения | https://student-clicker.onrender.com/metrics |
| Grafana (дашборд «Student Clicker») | https://organic-space-cod-wrjwgrqpvjgv2vg-3000.app.github.dev/ |
| Prometheus | https://organic-space-cod-wrjwgrqpvjgv2vg-9090.app.github.dev/ |

Что нужно знать при проверке:

- **Приложение** работает на Render (бесплатный план). После 15 минут без запросов сервис засыпает, первый заход тогда занимает до минуты.
- **Grafana и Prometheus** запущены в GitHub Codespaces и работают, пока он включён. Если ссылка не открывается, Codespace остановлен: напишите мне, и я его запущу.
- Grafana открывается без входа, в режиме просмотра. Дашборд находится в меню **Dashboards → Student Clicker**.
- Панели «память хоста» и «диск хоста» показывают машину, где запущен мониторинг (Codespace), а не Render.

## Как всё устроено

```
git push (main)
   │
   ├─► GitHub Actions: тест → сборка образа → GHCR (артефакт)
   │
   └─► Render: сборка по Dockerfile → приложение (https://student-clicker.onrender.com)
                                          ▲
                                          │ метрики каждые 10 секунд
                       Codespaces: Prometheus ──► Grafana (дашборд)
```

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

В этом режиме всё работает локально: приложение, Prometheus, Grafana, cAdvisor и node-exporter. Файл `prometheus.yml` собирает метрики с контейнера `clicker` внутри сети compose.

### Запуск мониторинга в GitHub Codespaces

В Codespaces не работает сеть между контейнерами: они не видят друг друга по именам. Поэтому там используется дополнительный файл, который запускает контейнеры в сети хоста. Приложение при этом берётся с Render, поэтому локальный контейнер `clicker` не запускается:

```bash
docker compose -f docker-compose.yml -f docker-compose.codespaces.yml up -d prometheus grafana node-exporter cadvisor
```

Файл `prometheus.codespaces.yml` собирает метрики приложения с адреса на Render, а метрики хоста берёт у node-exporter и cAdvisor через `localhost`. После запуска нужно открыть порты 3000 и 9090 (Public) во вкладке «Порты».

## Состав проекта

| Файл | Назначение |
|---|---|
| `app.py` | Приложение (Flask) и метрики |
| `Dockerfile` | Описание контейнера |
| `docker-compose.yml` | Приложение, Prometheus, Grafana, cAdvisor, node-exporter |
| `docker-compose.codespaces.yml` | Добавка для запуска в Codespaces (сеть хоста) |
| `prometheus.yml` | Сбор метрик при локальном запуске |
| `prometheus.codespaces.yml` | Сбор метрик в Codespaces (приложение на Render) |
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
- Прогресс сохраняется в файл `/data/state.json` в томе `clicker_data`. При запуске через compose он переживает перезапуск контейнера. На бесплатном плане Render постоянного диска нет, поэтому там прогресс сбрасывается при перезапуске сервиса.
- Приложение запускается через gunicorn с одним воркером: состояние игры хранится в памяти процесса.

## CI/CD: как это работает

1. **Исходники** лежат в git. Разработчик делает `git push` в ветку `main`.
2. **Сборка и проверка (CI).** Пайплайн GitHub Actions ставит зависимости и запускает smoke-тест: `/health`, главная страница, клик, наличие метрик.
3. **Артефакт.** Пайплайн собирает Docker-образ и сохраняет его в реестре GitHub (GHCR) с двумя тегами: `latest` и хэш коммита. Хэш позволяет откатиться на любую версию. Образ виден в разделе Packages репозитория.
4. **Деплой (CD).** Render следит за веткой `main`: после push он собирает образ по `Dockerfile` и выкатывает новую версию приложения.
5. **Деплой на свой сервер.** Для обычного сервера в репозитории есть скрипт `scripts/deploy.sh`: он скачивает образ из реестра, перезапускает контейнеры и проверяет `/health`. В пайплайне этот шаг (job `deploy`, запуск по SSH) выключен и показывается как skipped. Чтобы включить его, нужно: выполнить на сервере `scripts/server-setup.sh` и заполнить `.env` (см. `.env.example`), добавить секреты репозитория `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY` и создать переменную `DEPLOY_ENABLED` со значением `true`.
6. **Сохранение.** При запуске через compose данные лежат в Docker-томах: прогресс игры (`clicker_data`), метрики (`prom_data`), настройки Grafana (`grafana_data`). После перезапуска они не теряются.

Изменить приложение просто: правим код, делаем push, пайплайн проверяет и собирает образ, а Render выкатывает новую версию.

## Метрики

| Требование | Где смотреть |
|---|---|
| Health check | `/health`; `HEALTHCHECK` в Dockerfile (`docker ps` показывает `healthy`); панель Health в Grafana (метрика `up`) |
| Посещений в час | `increase(student_page_visits_total[1h])`; считает только заходы на главную страницу |
| Ресурсы потребляемые | CPU и память приложения (метрики процесса `process_cpu_seconds_total`, `process_resident_memory_bytes`); данные контейнера из cAdvisor, когда он их отдаёт |
| Ресурсы доступные | Память и диск хоста: доступно и всего (node-exporter) |
| Использование приложения | Клики, уровни, XP, запросы по endpoint, латентность |

Служебные запросы `/metrics` и `/health` в счётчик запросов не попадают.

## Сервисы

| Сервис | Порт | Где работает | Назначение |
|---|---|---|---|
| `clicker` | 5000 | Render (локально: compose) | Приложение и метрики |
| `prometheus` | 9090 | Codespaces (локально: compose) | Сбор и хранение метрик |
| `grafana` | 3000 | Codespaces (локально: compose) | Дашборд |
| `cadvisor` | 8080 (в Codespaces 8081) | Codespaces (локально: compose) | Метрики контейнеров |
| `node-exporter` | 9100 | Codespaces (локально: compose) | Метрики хоста |

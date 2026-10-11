#!/usr/bin/env bash
# Изолированный демо-стенд: свой проект Compose `calibr-demo`, свои тома и порты со сдвигом на
# сотню (фронт 3100, API 8100, Keycloak 8180, Mailpit 8125). Основной стенд и чужие контейнеры
# не затрагиваются.
#
#   scripts/demo.sh up      собрать, поднять в режиме жюри и засеять демо-данные
#   scripts/demo.sh seed    повторный засев — ничего не дублирует
#   scripts/demo.sh down    снести только проект calibr-demo вместе с его томами
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT=calibr-demo
export FRONTEND_PORT=${DEMO_FRONTEND_PORT:-3100}
export BACKEND_PORT=${DEMO_BACKEND_PORT:-8100}
export KEYCLOAK_PORT=${DEMO_KEYCLOAK_PORT:-8180}
export MAILPIT_UI_PORT=${DEMO_MAILPIT_UI_PORT:-8125}
export MAILPIT_SMTP_PORT=${DEMO_MAILPIT_SMTP_PORT:-1125}
export POSTGRES_PORT=${DEMO_POSTGRES_PORT:-5532}
export FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
export DEMO_MODE=true
export SESSION_COOKIE_NAME=${DEMO_SESSION_COOKIE_NAME:-calibr_demo_session}

compose() { docker compose -p "$PROJECT" "$@"; }

check_ports() {
  if [ -n "$(compose ps -q 2>/dev/null)" ]; then return; fi
  for port in "$FRONTEND_PORT" "$BACKEND_PORT" "$KEYCLOAK_PORT" "$MAILPIT_UI_PORT" \
    "$MAILPIT_SMTP_PORT" "$POSTGRES_PORT"; do
    if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Порт $port занят чужим процессом: задайте другой через DEMO_*_PORT" >&2
      exit 1
    fi
  done
}

wait_backend() {
  for _ in $(seq 1 120); do
    if curl -fsS "http://localhost:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then return; fi
    sleep 2
  done
  echo "Бэкенд не поднялся за 4 минуты" >&2
  exit 1
}

case "${1:-}" in
  up)
    check_ports
    compose up -d --build
    wait_backend
    compose exec -T backend python seed_demo.py
    echo "Интерфейс: $FRONTEND_URL  Mailpit: http://localhost:${MAILPIT_UI_PORT}"
    ;;
  seed)
    compose exec -T backend python seed_demo.py
    ;;
  down)
    compose down -v
    ;;
  *)
    echo "Использование: scripts/demo.sh up|seed|down" >&2
    exit 2
    ;;
esac

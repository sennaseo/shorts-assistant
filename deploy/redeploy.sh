#!/usr/bin/env bash
# 재배포: ~/shorts-assistant/deploy/redeploy.sh — 코드 받고 → 빌드 → 띄우고 → nginx conf 갱신.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
[ -f "$ROOT/.env" ] || { echo "!! $ROOT/.env 가 없다. .env.example 를 복사해 채울 것"; exit 1; }
[ -e "$ROOT/deploy/.env" ] || ln -s ../.env "$ROOT/deploy/.env"
git pull
(cd "$ROOT/deploy" && docker compose build && docker compose up -d)
DOMAIN=$(grep -E '^DOMAIN=' "$ROOT/.env" | cut -d= -f2-)
[ -n "$DOMAIN" ] || { echo "!! .env 의 DOMAIN 이 비어 있다"; exit 1; }
sed "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" "$ROOT/deploy/nginx/shorts.conf" > "$ROOT/deploy/nginx/shorts.generated.conf"
docker exec bbanggu-web nginx -t && docker exec bbanggu-web nginx -s reload
echo "== 배포 완료 =="
(cd "$ROOT/deploy" && docker compose ps)

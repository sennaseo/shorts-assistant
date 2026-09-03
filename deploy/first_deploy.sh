#!/usr/bin/env bash
# 서버 첫 배포 한 방: 인증서 → 컨테이너 → 공유 nginx 마운트. 다시 돌려도 안전.
# 실행: ~/shorts-assistant/deploy/first_deploy.sh
# 전제: ~/shorts-assistant/.env 에 DOMAIN·APP_PASSWORD·API 키가 채워져 있고, bbanggu-web 이 떠 있다.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2-)
[ -n "$DOMAIN" ] || { echo "!! .env 의 DOMAIN 이 비어 있다"; exit 1; }
grep -qE '^APP_PASSWORD=.+' .env || { echo "!! .env 의 APP_PASSWORD 가 비어 있다 — 인터넷에 열리므로 필수"; exit 1; }
[ -e deploy/.env ] || ln -s ../.env deploy/.env
docker network inspect proxy-net >/dev/null 2>&1 || docker network create proxy-net

echo "== 1. 인증서 ($DOMAIN)"
if docker run --rm --entrypoint test -v bbanggu_certbot_conf:/etc/letsencrypt certbot/certbot \
     -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem"; then
  echo "이미 있음, 건너뜀"
else
  docker run --rm --entrypoint certbot \
    -v bbanggu_certbot_conf:/etc/letsencrypt -v bbanggu_certbot_www:/var/www/certbot \
    certbot/certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" \
    --non-interactive --agree-tos --register-unsafely-without-email
fi

echo "== 2. 컨테이너"
(cd deploy && docker compose build && docker compose up -d)

echo "== 3. 공유 nginx (bbanggu-web)"
GEN="$ROOT/deploy/nginx/shorts.generated.conf"
sed "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" deploy/nginx/shorts.conf > "$GEN"
BB="$HOME/BBANGGU/docker-compose.yml"
if ! grep -qF "shorts.generated.conf" "$BB"; then
  cp "$BB" "$BB.bak-shorts"
  # reelradar 마운트 줄 뒤에 한 줄 끼운다 (reelradar 가 없으면 boindang 뒤).
  ANCHOR=$(grep -q "reelradar.conf:ro" "$BB" && echo "reelradar.conf:ro" || echo "boindang.conf:/etc/nginx/conf.d/boindang.conf:ro")
  sed -i "\#$ANCHOR#a\\      - $GEN:/etc/nginx/conf.d/shorts.conf:ro" "$BB"
  (cd "$HOME/BBANGGU" && docker compose up -d --no-deps web)
  sleep 3
fi
docker exec bbanggu-web nginx -t && docker exec bbanggu-web nginx -s reload

echo "== 배포 완료 == https://$DOMAIN"
(cd deploy && docker compose ps)

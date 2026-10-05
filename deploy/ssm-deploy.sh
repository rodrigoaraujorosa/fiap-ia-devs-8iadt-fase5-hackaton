#!/usr/bin/env bash
# Deploy na EC2 pelo SSM Run Command (sem SSH, sem porta 22): chamado pelo GitHub Actions com credenciais
# temporárias (OIDC). Grava o compose e o Caddyfile em /opt/imobiq, baixa as imagens da versão do commit,
# sobe os containers, espera a API ficar saudável e roda o seed (idempotente: só insere o que falta).
# Com a instância parada (fora dos testes e da demo), não falha: avisa e marca skipped=true para o workflow.
set -euo pipefail
: "${INSTANCE_ID:?defina INSTANCE_ID}" "${IMAGE_TAG:?defina IMAGE_TAG}" "${AWS_REGION:?defina AWS_REGION}"

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com"
COMPOSE_B64=$(base64 -w0 deploy/docker-compose.prod.yml)
CADDY_B64=$(base64 -w0 deploy/Caddyfile)

# script executado na EC2 (as variáveis acima são expandidas aqui; \$ fica para o servidor)
REMOTE=$(cat <<EOF
set -euo pipefail
cd /opt/imobiq
test -f .env || { echo "Falta /opt/imobiq/.env (modelo em deploy/production.env.example)"; exit 1; }
echo "$COMPOSE_B64" | base64 -d > docker-compose.prod.yml
echo "$CADDY_B64" | base64 -d > Caddyfile
printf 'REGISTRY=%s\nIMAGE_TAG=%s\n' "$REGISTRY" "$IMAGE_TAG" > release.env
printf '#!/bin/sh\ncd /opt/imobiq && exec docker compose --env-file .env --env-file release.env -f docker-compose.prod.yml "\$@"\n' > dc
chmod +x dc
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
./dc pull
./dc up -d --remove-orphans
echo "Esperando a API (migrations)..."
for i in \$(seq 1 60); do
  if ./dc exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    break
  fi
  sleep 5
done
./dc exec -T api python -m scripts.seed
docker image prune -af --filter until=168h >/dev/null
./dc ps
EOF
)

PARAMS=$(jq -n --arg script "$REMOTE" '{commands: [$script], executionTimeout: ["1800"]}')
if ! COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "imobiq ${IMAGE_TAG:0:7}" \
  --parameters "$PARAMS" \
  --query Command.CommandId --output text 2>send-command.err); then
  cat send-command.err >&2
  # o SSM recusa com InvalidInstanceId quando a instância não está em execução (ou sem o agente no ar)
  if grep -q InvalidInstanceId send-command.err; then
    MSG="Instância $INSTANCE_ID parada: as imagens ${IMAGE_TAG:0:7} estão no ECR, mas a EC2 não foi atualizada."
    echo "::warning title=Deploy pulado::$MSG Ligue a instância e rode Actions -> Deploy -> Run workflow."
    echo "skipped=true" >> "${GITHUB_OUTPUT:-/dev/null}"
    printf '### ⏸️ Deploy pulado\n\n%s\n\nLigue a instância e rode **Actions → Deploy → Run workflow**.\n' "$MSG" \
      >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
    exit 0
  fi
  exit 1
fi
echo "Comando SSM: $COMMAND_ID"

STATUS=Pending
for _ in $(seq 1 120); do
  sleep 10
  STATUS=$(aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
    --query Status --output text 2>/dev/null || echo Pending)
  case "$STATUS" in Success | Failed | Cancelled | TimedOut) break ;; esac
done

echo "----- saída na EC2 -----"
aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query StandardOutputContent --output text || true
echo "----- erros -----"
aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query StandardErrorContent --output text || true
echo "Status: $STATUS"
[ "$STATUS" = Success ]

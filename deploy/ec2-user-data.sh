#!/bin/bash
# Preparação da EC2 (Amazon Linux 2023). Cole em "Advanced details → User data" ao criar a instância:
# roda uma vez, no primeiro boot. O agente do SSM já vem instalado no Amazon Linux 2023.
set -euxo pipefail

# Docker + Compose
dnf install -y docker
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Swap de 2 GB: folga de memória para a t3.small (2 GB de RAM)
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

# Pasta do app: o deploy grava aqui o compose, o Caddyfile e o release.env; o .env de produção é criado à mão
mkdir -p /opt/imobiq
chmod 750 /opt/imobiq

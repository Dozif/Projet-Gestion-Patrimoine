#!/usr/bin/env bash
# Crée l'archive à copier sur le Synology (contenu du dernier commit : ni .env, ni base, ni justificatifs).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
nom="dist/patrimoine-$(date +%Y%m%d)-$(git rev-parse --short HEAD).zip"
git archive --format=zip --prefix=patrimoine/ -o "$nom" HEAD
echo "$nom"

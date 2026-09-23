#!/usr/bin/env bash
set -euo pipefail
exec docker run --rm -i --user "$(id -u)" \
  --volume "$PWD":/app --workdir /app \
  --volume "$HOME/.config/helm/registry/":/helm/registry \
  --env HELM_REGISTRY_CONFIG=/helm/registry/config.json \
  "$HELM_IMAGE:$HELM_VERSION" helm "$@"
#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-profile-service}"
TAG="${TAG:-1.0.0}"
REGISTRY="${REGISTRY:-}"

if [[ -n "${REGISTRY}" ]]; then
    full="${REGISTRY}/${IMAGE}:${TAG}"
else
    full="${IMAGE}:${TAG}"
fi

echo "building ${full}"
docker build --tag "${full}" --file Dockerfile .

if [[ "${PUSH:-0}" == "1" ]]; then
    echo "pushing ${full}"
    docker push "${full}"
fi

echo "image: ${full}"

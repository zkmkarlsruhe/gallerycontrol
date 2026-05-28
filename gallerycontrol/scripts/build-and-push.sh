#!/bin/bash

# Build and push script for GalleryControl

set -e

# Configuration
IMAGE_NAME="${IMAGE_NAME:-gallerycontrol}"
REGISTRY="${REGISTRY:-registry.example.com}"

# Get git version tag, fallback to 'dev' if no tag
if git describe --tags --exact-match HEAD 2>/dev/null; then
    TAG=$(git describe --tags --exact-match HEAD)
elif git rev-parse --verify HEAD >/dev/null 2>&1; then
    TAG="dev-$(git rev-parse --short HEAD)"
else
    TAG="dev"
fi

FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"
LATEST_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:latest"

echo "=== Building Docker image ==="
echo "Image: ${FULL_IMAGE_NAME}"
echo "Git tag/commit: ${TAG}"
echo "=============================="

# Build the image
docker build -t "${FULL_IMAGE_NAME}" -t "${LATEST_IMAGE_NAME}" .

echo ""
echo "=== Build completed ==="
docker images "${REGISTRY}/${IMAGE_NAME}"

echo ""
echo "=== Pushing to Harbor ==="
echo "Pushing: ${FULL_IMAGE_NAME}"
docker push "${FULL_IMAGE_NAME}"

echo "Pushing: ${LATEST_IMAGE_NAME}"
docker push "${LATEST_IMAGE_NAME}"

echo ""
echo "=== Push completed ==="
echo "Images pushed:"
echo "  - ${FULL_IMAGE_NAME}"
echo "  - ${LATEST_IMAGE_NAME}"

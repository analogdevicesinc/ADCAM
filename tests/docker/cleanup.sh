#!/bin/bash

# Cleanup Docker resources for ADCAM testing

set -e

echo "Cleaning up ADCAM test Docker resources..."

# Stop and remove containers
echo "Stopping containers..."
docker-compose down 2>/dev/null || true
docker stop adcam-test-container 2>/dev/null || true
docker rm adcam-test-container 2>/dev/null || true

# Remove image
echo "Removing Docker image..."
docker rmi adcam-test:latest 2>/dev/null || true

# Clean temporary files
echo "Cleaning temporary files..."
rm -rf ./local_code 2>/dev/null || true
rm -rf ./libs 2>/dev/null || true
rm -f ./build_output.log 2>/dev/null || true

echo "✓ Cleanup complete!"

#!/bin/bash

echo "Cleaning up Docker artifacts from ADCAM build tests..."

# Remove the specific image if it exists
if sudo docker images | grep -q adcam-build-test; then
    echo "Removing adcam-build-test image..."
    sudo docker image rm adcam-build-test
fi

# Remove any other custom tagged images
for tag in $(sudo docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "^adcam-|^my-test"); do
    echo "Removing image: $tag"
    sudo docker image rm "$tag"
done

# Clean up dangling images and build cache
echo "Cleaning up dangling images and build cache..."
sudo docker system prune -f

# Remove local folders used for Docker build context
if [ -d "./libs" ]; then
    echo "Removing ./libs folder..."
    rm -rf ./libs
fi

if [ -d "./local_code" ]; then
    echo "Removing ./local_code folder..."
    rm -rf ./local_code
fi

# Remove build log file
if [ -f "./build_output.log" ]; then
    echo "Removing build_output.log..."
    rm -f ./build_output.log
fi

echo ""
echo "✓ Docker cleanup complete!"
echo ""
echo "To see remaining images:"
echo "  sudo docker images"

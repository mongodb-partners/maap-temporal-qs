#!/bin/ksh
export AWS_ACCESS_KEY_ID=""
export AWS_SECRET_ACCESS_KEY=""
export AWS_SESSION_TOKEN=""

set -e  # Exit immediately if a command exits with a non-zero status
AWS_PUBLIC_ECR="public.ecr.aws/s2e1n3u8"
AWS_REGION=$(aws configure get region)
aws ecr-public get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_PUBLIC_ECR
services=(
    "maap-temporal-qs-host"
    "maap-temporal-qs-data-loader"
    "maap-temporal-qs-event-logger"
    "maap-temporal-qs-ai-memory"
    "maap-temporal-qs-semantic-cache"
)
cd MAAP-Temporal
# Ensure Docker Buildx is enabled for multi-platform builds
docker buildx create --use || echo "Buildx already enabled"
for service in "${services[@]}"; do
    echo "======================================"
    sub_service="${service#maap-temporal-qs-}"
    cd "$sub_service"
    
    # Create repository if it doesn't exist
    echo "Creating repository for $service if it doesn't exist..."
    aws ecr-public describe-repositories --region $AWS_REGION --repository-names $service >/dev/null 2>&1 || \
    aws ecr-public create-repository --repository-name $service --region $AWS_REGION
    
    echo "🚀 Building and pushing multi-platform image for $service..."
    docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --tag "$AWS_PUBLIC_ECR/$service:latest" \
    --push .
    cd ..
    echo "======================================"
done
echo "🎉 All images pushed successfully!"
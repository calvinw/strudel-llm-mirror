#!/bin/bash

# Docker build script for Strudel
# Usage: ./docker-build.sh [dev|prod|both]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_usage() {
    echo "Usage: $0 [dev|prod|both]"
    echo ""
    echo "  dev   - Build development container (Dockerfile.dev)"
    echo "  prod  - Build production container (Dockerfile)"
    echo "  both  - Build both containers (default)"
    echo ""
    echo "Examples:"
    echo "  $0 dev"
    echo "  $0 prod"
    echo "  $0"
}

build_dev() {
    echo -e "${YELLOW}Building development container...${NC}"
    docker build -f Dockerfile.dev -t strudel-dev .
    echo -e "${GREEN}✓ Development container built: strudel-dev${NC}"
    echo -e "${YELLOW}Run with: docker run -p 4321:4321 strudel-dev${NC}"
}

build_prod() {
    echo -e "${YELLOW}Building production container...${NC}"
    docker build -t strudel-prod .
    echo -e "${GREEN}✓ Production container built: strudel-prod${NC}"
    echo -e "${YELLOW}Run with: docker run -p 8080:8080 strudel-prod${NC}"
}

# Default to both if no argument provided
TARGET=${1:-both}

case $TARGET in
    dev)
        build_dev
        ;;
    prod)
        build_prod
        ;;
    both)
        build_dev
        echo ""
        build_prod
        ;;
    help|--help|-h)
        print_usage
        exit 0
        ;;
    *)
        echo -e "${RED}Error: Unknown option '$TARGET'${NC}"
        echo ""
        print_usage
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}🎵 Docker build complete!${NC}"
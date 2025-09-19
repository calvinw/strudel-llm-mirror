#!/bin/bash

# Sync script to push changes from Codeberg to GitHub mirror
# Usage: ./sync-to-github.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Syncing Strudel to GitHub mirror...${NC}"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo -e "${RED}❌ Error: Not in a git repository${NC}"
    exit 1
fi

# Add GitHub remote if it doesn't exist
if ! git remote get-url github &> /dev/null; then
    echo -e "${YELLOW}Adding GitHub remote...${NC}"
    git remote add github https://github.com/calvinw/strudel-llm-mirror.git
else
    echo -e "${GREEN}✓ GitHub remote already configured${NC}"
fi

# Fetch latest from origin (Codeberg)
echo -e "${YELLOW}📥 Fetching latest from Codeberg...${NC}"
git fetch origin

# Check if we're on main branch
current_branch=$(git branch --show-current)
if [ "$current_branch" != "main" ]; then
    echo -e "${YELLOW}⚠️  Currently on branch: $current_branch${NC}"
    echo -e "${YELLOW}Switching to main branch...${NC}"
    git checkout main
fi

# Pull latest changes and handle conflicts
echo -e "${YELLOW}📥 Merging changes from Codeberg...${NC}"
if ! git pull origin main; then
    echo -e "${RED}❌ Merge conflicts detected. Please resolve manually.${NC}"
    exit 1
fi

# Push to GitHub mirror
echo -e "${YELLOW}📤 Pushing to GitHub mirror...${NC}"
if ! git push github main; then
    echo -e "${YELLOW}⚠️  Push failed. Trying to merge GitHub changes first...${NC}"
    git fetch github
    git merge github/main
    git push github main
fi

echo -e "${GREEN}✅ Successfully synced to GitHub mirror!${NC}"
echo -e "${YELLOW}GitHub repo: https://github.com/calvinw/strudel-llm-mirror${NC}"
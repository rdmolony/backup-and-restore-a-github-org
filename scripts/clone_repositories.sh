#!/run/current-system/sw/bin/bash

# Script to clone all repositories from any GitHub organization
set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <organization> <backup_directory>"
    echo "Example: $0 powerscope /home/user/backup"
    exit 1
fi

ORG="$1"
BACKUP_DIR="$2/repositories"

echo "Starting repository cloning process..."
echo "Organization: $ORG"
echo "Backup directory: $BACKUP_DIR"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Get list of all repositories in the organization
echo "Discovering repositories in $ORG organization..."
REPOS=($(nix run nixpkgs#gh -- repo list "$ORG" --limit 1000 --json name --jq '.[].name'))

echo "Found ${#REPOS[@]} repositories to clone"

cd "$BACKUP_DIR"

for repo in "${REPOS[@]}"; do
    echo "Cloning $ORG/$repo..."
    if [ -d "$repo" ]; then
        echo "  Repository $repo already exists, skipping..."
    else
        nix run nixpkgs#gh -- repo clone "$ORG/$repo" -- --recurse-submodules
        if [ $? -eq 0 ]; then
            echo "  ✓ Successfully cloned $repo"
        else
            echo "  ✗ Failed to clone $repo"
        fi
    fi
done

echo "Repository cloning completed!"
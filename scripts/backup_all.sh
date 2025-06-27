#!/run/current-system/sw/bin/bash

# Master script to run complete backup of any GitHub organization
set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <organization> <backup_directory>"
    exit 1
fi

ORG="$1"
BACKUP_DIR="$2"
SCRIPT_DIR="$(dirname "$0")"

echo "======================================="
echo "STARTING COMPLETE GITHUB ORGANIZATION BACKUP"
echo "Organization: $ORG"
echo "Backup Directory: $BACKUP_DIR"
echo "$(date)"
echo "======================================="

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Make all scripts executable
chmod +x "$SCRIPT_DIR"/*.sh

echo ""
echo "Step 1: Cloning all repositories..."
"$SCRIPT_DIR/clone_repositories.sh" "$ORG" "$BACKUP_DIR"

echo ""
echo "Step 2: Exporting all issues..."
"$SCRIPT_DIR/export_issues.sh" "$ORG" "$BACKUP_DIR"

echo ""
echo "Step 3: Exporting all pull requests..."
"$SCRIPT_DIR/export_pull_requests.sh" "$ORG" "$BACKUP_DIR"

echo ""
echo "======================================="
echo "BACKUP COMPLETED SUCCESSFULLY"
echo "Organization: $ORG"
echo "$(date)"
echo "======================================="
echo ""
echo "Backup contents:"
echo "- Repositories: $BACKUP_DIR/repositories/"
echo "- Issues: $BACKUP_DIR/issues/"
echo "- Pull Requests: $BACKUP_DIR/pull-requests/"
echo ""
echo "Total:"
if [ -d "$BACKUP_DIR/repositories" ]; then
    ls -la "$BACKUP_DIR/repositories/" | wc -l | awk '{print "- " ($1-3) " repositories cloned"}'
fi
if [ -d "$BACKUP_DIR/issues" ]; then
    ls -la "$BACKUP_DIR/issues/"*.json 2>/dev/null | wc -l | awk '{print "- " $1 " issue files exported"}'
fi
if [ -d "$BACKUP_DIR/pull-requests" ]; then
    ls -la "$BACKUP_DIR/pull-requests/"*.json 2>/dev/null | wc -l | awk '{print "- " $1 " pull request files exported"}'
fi
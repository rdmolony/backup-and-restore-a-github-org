#!/run/current-system/sw/bin/bash

# Complete organization migration script - backup and migrate in one step
set -e

if [ $# -ne 3 ]; then
    echo "Usage: $0 <source_organization> <target_organization> <backup_directory>"
    echo ""
    echo "This script performs a complete migration:"
    echo "1. Backs up all data from source organization"
    echo "2. Migrates everything to target organization"
    echo "3. Respects GitHub API rate limits"
    exit 1
fi

SOURCE_ORG="$1"
TARGET_ORG="$2"
BACKUP_DIR="$3"
SCRIPT_DIR="$(dirname "$0")"

echo "======================================="
echo "COMPLETE GITHUB ORGANIZATION MIGRATION"
echo "Source: $SOURCE_ORG"
echo "Target: $TARGET_ORG"
echo "Backup Directory: $BACKUP_DIR"
echo "$(date)"
echo "======================================="

# Make all scripts executable
chmod +x "$SCRIPT_DIR"/*.sh

echo ""
echo "PHASE 1: BACKING UP SOURCE ORGANIZATION"
echo "======================================="
"$SCRIPT_DIR/backup_all.sh" "$SOURCE_ORG" "$BACKUP_DIR"

echo ""
echo "PHASE 2: MIGRATING TO TARGET ORGANIZATION"
echo "======================================="
"$SCRIPT_DIR/migrate_with_rate_limits.sh" "$SOURCE_ORG" "$TARGET_ORG" "$BACKUP_DIR"

echo ""
echo "======================================="
echo "COMPLETE MIGRATION FINISHED!"
echo "Source: $SOURCE_ORG"
echo "Target: $TARGET_ORG"
echo "$(date)"
echo "======================================="
echo ""
echo "Summary:"
echo "- Source data backed up to: $BACKUP_DIR"
echo "- Target organization: https://github.com/$TARGET_ORG"
echo "- Migration log: $BACKUP_DIR/migration_log.txt"
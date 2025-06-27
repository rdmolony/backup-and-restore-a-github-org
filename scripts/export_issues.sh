#!/run/current-system/sw/bin/bash

# Script to export all issues from any GitHub organization repositories
set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <organization> <backup_directory>"
    echo "Example: $0 powerscope /home/user/backup"
    exit 1
fi

ORG="$1"
BACKUP_DIR="$2/issues"

echo "Starting issues export process..."
echo "Organization: $ORG"
echo "Backup directory: $BACKUP_DIR"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Get list of all repositories in the organization
echo "Discovering repositories in $ORG organization..."
REPOS=($(nix run nixpkgs#gh -- repo list "$ORG" --limit 1000 --json name --jq '.[].name'))

echo "Found ${#REPOS[@]} repositories to process"

cd "$BACKUP_DIR"

for repo in "${REPOS[@]}"; do
    echo "Exporting issues from $ORG/$repo..."
    
    # Export issues using GitHub API
    nix run nixpkgs#gh -- api graphql --paginate -f query="
    query(\$owner: String!, \$repo: String!, \$cursor: String) {
      repository(owner: \$owner, name: \$repo) {
        issues(first: 100, after: \$cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            number
            title
            body
            state
            createdAt
            updatedAt
            closedAt
            author {
              login
            }
            assignees(first: 10) {
              nodes {
                login
              }
            }
            labels(first: 20) {
              nodes {
                name
                color
                description
              }
            }
            comments(first: 100) {
              nodes {
                body
                createdAt
                author {
                  login
                }
              }
            }
          }
        }
      }
    }" -f owner="$ORG" -f repo="$repo" > "${repo}_issues.json"
    
    if [ $? -eq 0 ]; then
        # Handle both GraphQL structure and empty responses
        if [ "$(nix run nixpkgs#jq -- 'type' "${repo}_issues.json")" = '"object"' ]; then
            actual_count=$(cat "${repo}_issues.json" | nix run nixpkgs#jq -- '.data.repository.issues.nodes | length')
        else
            actual_count=0
            echo "[]" > "${repo}_issues.json"
        fi
        echo "  ✓ Successfully exported $actual_count issues from $repo"
    else
        echo "  ✗ Failed to export issues from $repo"
        echo "[]" > "${repo}_issues.json"
    fi
done

echo "Issues export completed!"
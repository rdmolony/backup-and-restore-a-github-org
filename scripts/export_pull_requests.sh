#!/run/current-system/sw/bin/bash

# Script to export all pull requests from any GitHub organization repositories
set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <organization> <backup_directory>"
    echo "Example: $0 powerscope /home/user/backup"
    exit 1
fi

ORG="$1"
BACKUP_DIR="$2/pull-requests"

echo "Starting pull requests export process..."
echo "Organization: $ORG"
echo "Backup directory: $BACKUP_DIR"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Get list of all repositories in the organization
echo "Discovering repositories in $ORG organization..."
REPOS=($(gh repo list "$ORG" --limit 1000 --json name --jq '.[].name'))

echo "Found ${#REPOS[@]} repositories to process"

cd "$BACKUP_DIR"

for repo in "${REPOS[@]}"; do
    echo "Exporting pull requests from $ORG/$repo..."
    
    # Export pull requests using GitHub API
    gh api graphql --paginate -f query="
    query(\$owner: String!, \$repo: String!, \$cursor: String) {
      repository(owner: \$owner, name: \$repo) {
        pullRequests(first: 100, after: \$cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
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
            mergedAt
            author {
              login
            }
            baseRefName
            headRefName
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
            reviews(first: 50) {
              nodes {
                state
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
    }" -f owner="$ORG" -f repo="$repo" > "${repo}_pull_requests.json"
    
    if [ $? -eq 0 ]; then
        # Handle both GraphQL structure and empty responses
        if [ "$(jq 'type' "${repo}_pull_requests.json")" = '"object"' ]; then
            actual_count=$(cat "${repo}_pull_requests.json" | jq '.data.repository.pullRequests.nodes | length')
        else
            actual_count=0
            echo "[]" > "${repo}_pull_requests.json"
        fi
        echo "  ✓ Successfully exported $actual_count pull requests from $repo"
    else
        echo "  ✗ Failed to export pull requests from $repo"
        echo "[]" > "${repo}_pull_requests.json"
    fi
done

echo "Pull requests export completed!"
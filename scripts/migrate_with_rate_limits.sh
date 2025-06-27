#!/run/current-system/sw/bin/bash

# Comprehensive migration script that respects GitHub API rate limits
# Rate limits: 20 issues per minute, 150 per hour, same for comments
set -e

if [ $# -ne 3 ]; then
    echo "Usage: $0 <source_organization> <target_organization> <backup_directory>"
    echo ""
    echo "This script migrates repositories, issues, and pull requests from one"
    echo "GitHub organization to another, respecting API rate limits."
    exit 1
fi

SOURCE_ORG="$1"
TARGET_ORG="$2"
BACKUP_BASE_DIR="$3"
SOURCE_REPOS_DIR="$BACKUP_BASE_DIR/repositories"
ISSUES_DIR="$BACKUP_BASE_DIR/issues"
PULLS_DIR="$BACKUP_BASE_DIR/pull-requests"
LOG_FILE="$BACKUP_BASE_DIR/migration_log.txt"

echo "======================================="
echo "GITHUB ORGANIZATION MIGRATION"
echo "Source: $SOURCE_ORG"
echo "Target: $TARGET_ORG"
echo "Backup Directory: $BACKUP_BASE_DIR"
echo "$(date)"
echo "======================================="

# Check if backup directories exist
if [ ! -d "$SOURCE_REPOS_DIR" ] || [ ! -d "$ISSUES_DIR" ] || [ ! -d "$PULLS_DIR" ]; then
    echo "Error: Backup directories not found!"
    echo "Please run the backup script first:"
    echo "  ./backup_all.sh $SOURCE_ORG $BACKUP_BASE_DIR"
    exit 1
fi

# Rate limiting counters
ISSUES_PER_MINUTE=0
COMMENTS_PER_MINUTE=0
HOUR_START=$(date +%s)
MINUTE_START=$(date +%s)
ISSUES_THIS_HOUR=0
COMMENTS_THIS_HOUR=0

# Discover repositories from backup directory
echo "Discovering repositories from backup..."
REPOS=()
if [ -d "$SOURCE_REPOS_DIR" ]; then
    for repo_dir in "$SOURCE_REPOS_DIR"/*; do
        if [ -d "$repo_dir" ]; then
            repo_name=$(basename "$repo_dir")
            REPOS+=("$repo_name")
        fi
    done
fi

if [ ${#REPOS[@]} -eq 0 ]; then
    echo "Error: No repositories found in $SOURCE_REPOS_DIR"
    echo "Please run the backup script first."
    exit 1
fi

echo "Found ${#REPOS[@]} repositories to migrate: ${REPOS[*]}"

# Sort repositories by complexity (number of issues + PRs)
declare -A REPO_COMPLEXITY
for repo in "${REPOS[@]}"; do
    issues_count=0
    prs_count=0
    
    # Count issues
    if [ -f "$ISSUES_DIR/${repo}_issues.json" ]; then
        if [ "$(jq 'type' "$ISSUES_DIR/${repo}_issues.json")" = '"object"' ]; then
            issues_count=$(jq '.data.repository.issues.nodes | length' "$ISSUES_DIR/${repo}_issues.json" 2>/dev/null || echo "0")
        fi
    fi
    
    # Count PRs
    if [ -f "$PULLS_DIR/${repo}_pull_requests.json" ]; then
        if [ "$(jq 'type' "$PULLS_DIR/${repo}_pull_requests.json")" = '"object"' ]; then
            prs_count=$(jq '.data.repository.pullRequests.nodes | length' "$PULLS_DIR/${repo}_pull_requests.json" 2>/dev/null || echo "0")
        fi
    fi
    
    REPO_COMPLEXITY["$repo"]=$((issues_count + prs_count))
done

# Sort repositories by complexity (simplest first)
SORTED_REPOS=($(for repo in "${!REPO_COMPLEXITY[@]}"; do
    echo "${REPO_COMPLEXITY[$repo]} $repo"
done | sort -n | cut -d' ' -f2))

echo "Migration order (by complexity):"
for repo in "${SORTED_REPOS[@]}"; do
    echo "  $repo (${REPO_COMPLEXITY[$repo]} items)"
done

# Function to wait for rate limit reset
wait_for_rate_limit() {
    local type=$1  # "issue" or "comment"
    local current_time=$(date +%s)
    
    # Check if we need to reset minute counters
    if [ $((current_time - MINUTE_START)) -ge 60 ]; then
        ISSUES_PER_MINUTE=0
        COMMENTS_PER_MINUTE=0
        MINUTE_START=$current_time
        echo "  [$(date '+%H:%M:%S')] Minute reset - issues: $ISSUES_PER_MINUTE, comments: $COMMENTS_PER_MINUTE"
    fi
    
    # Check if we need to reset hour counters
    if [ $((current_time - HOUR_START)) -ge 3600 ]; then
        ISSUES_THIS_HOUR=0
        COMMENTS_THIS_HOUR=0
        HOUR_START=$current_time
        echo "  [$(date '+%H:%M:%S')] Hour reset - issues: $ISSUES_THIS_HOUR, comments: $COMMENTS_THIS_HOUR"
    fi
    
    # Wait if we're approaching limits
    if [ "$type" = "issue" ]; then
        if [ $ISSUES_PER_MINUTE -ge 18 ]; then
            echo "  [$(date '+%H:%M:%S')] Approaching issue rate limit (18/20 per minute), waiting..."
            sleep 65
            ISSUES_PER_MINUTE=0
            MINUTE_START=$(date +%s)
        elif [ $ISSUES_THIS_HOUR -ge 140 ]; then
            echo "  [$(date '+%H:%M:%S')] Approaching hourly issue limit (140/150), waiting..."
            sleep 3660
            ISSUES_THIS_HOUR=0
            HOUR_START=$(date +%s)
        else
            sleep 4  # 3 second delay between issues to be safe
        fi
    elif [ "$type" = "comment" ]; then
        if [ $COMMENTS_PER_MINUTE -ge 18 ]; then
            echo "  [$(date '+%H:%M:%S')] Approaching comment rate limit (18/20 per minute), waiting..."
            sleep 65
            COMMENTS_PER_MINUTE=0
            MINUTE_START=$(date +%s)
        elif [ $COMMENTS_THIS_HOUR -ge 140 ]; then
            echo "  [$(date '+%H:%M:%S')] Approaching hourly comment limit (140/150), waiting..."
            sleep 3660
            COMMENTS_THIS_HOUR=0
            HOUR_START=$(date +%s)
        else
            sleep 4  # 3 second delay between comments to be safe
        fi
    fi
}

# Function to create repository
create_repository() {
    local repo_name=$1
    local original_dir=$(pwd)
    
    echo "=== Creating repository: $TARGET_ORG/$repo_name ==="
    
    # Check if repository already exists
    if gh repo view "$TARGET_ORG/$repo_name" >/dev/null 2>&1; then
        echo "  ✓ Repository already exists, skipping creation and content push"
        return 2  # Special return code for "already exists"
    fi
    
    # Create the repository
    if gh repo create "$TARGET_ORG/$repo_name" --private --description "Migrated from powerscope organization" --clone=false; then
        echo "  ✓ Repository created successfully"
    else
        echo "  ✗ Failed to create repository"
        return 1
    fi
    
    # Push repository content
    echo "  Pushing repository content..."
    cd "$SOURCE_REPOS_DIR/$repo_name"
    
    # Check if this repo has LFS files
    if [ -f ".gitattributes" ]; then
        echo "    LFS detected, fetching LFS objects..."
        git lfs fetch --all >/dev/null 2>&1 || echo "    LFS fetch completed with warnings"
    fi
    
    # Add the new remote and push
    git remote add thalora "https://github.com/$TARGET_ORG/$repo_name.git" 2>/dev/null || true
    git push thalora --all --force >/dev/null 2>&1
    git push thalora --tags --force >/dev/null 2>&1
    git remote remove thalora 2>/dev/null || true
    
    echo "  ✓ Repository content pushed successfully"
    cd "$original_dir"
}

# Function to create issues with comments
create_issues() {
    local repo_name=$1
    
    echo "  Creating issues for $repo_name..."
    
    if [ ! -f "$ISSUES_DIR/${repo_name}_issues.json" ]; then
        echo "    No issues file found"
        return 0
    fi
    
    # Handle both GraphQL structure and empty array
    local issue_count
    if [ "$(jq 'type' "$ISSUES_DIR/${repo_name}_issues.json")" = '"array"' ]; then
        issue_count=$(jq 'length' "$ISSUES_DIR/${repo_name}_issues.json")
    else
        issue_count=$(jq '.data.repository.issues.nodes | length' "$ISSUES_DIR/${repo_name}_issues.json")
    fi
    
    if [ "$issue_count" -eq 0 ]; then
        echo "    No issues to create"
        return 0
    fi
    
    echo "    Creating $issue_count issues..."
    
    # Process each issue (skip if empty array)
    if [ "$issue_count" -eq 0 ]; then
        return 0
    fi
    
    local issue_index=0
    if [ "$(jq 'type' "$ISSUES_DIR/${repo_name}_issues.json")" = '"array"' ]; then
        # Empty array, no issues to process
        return 0
    else
        jq -c '.data.repository.issues.nodes[]' "$ISSUES_DIR/${repo_name}_issues.json" | while read -r issue_json; do
        issue_index=$((issue_index + 1))
        
        # Extract issue data
        local title=$(echo "$issue_json" | jq -r '.title')
        local body=$(echo "$issue_json" | jq -r '.body // ""')
        local state=$(echo "$issue_json" | jq -r '.state')
        local comments=$(echo "$issue_json" | jq -c '.comments.nodes[]' 2>/dev/null || echo "")
        
        echo "    [$issue_index/$issue_count] Creating: $title"
        
        # Wait for rate limit
        wait_for_rate_limit "issue"
        
        # Create the issue
        local issue_url=""
        if [ "$state" = "OPEN" ]; then
            issue_url=$(gh issue create --repo "$TARGET_ORG/$repo_name" --title "$title" --body "$body" 2>/dev/null)
        else
            issue_url=$(gh issue create --repo "$TARGET_ORG/$repo_name" --title "$title" --body "$body" 2>/dev/null)
        fi
        
        if [ $? -eq 0 ]; then
            ISSUES_PER_MINUTE=$((ISSUES_PER_MINUTE + 1))
            ISSUES_THIS_HOUR=$((ISSUES_THIS_HOUR + 1))
            
            local issue_number=$(echo "$issue_url" | sed 's/.*\///')
            echo "      ✓ Created issue #$issue_number"
            
            # Add comments if any
            if [ -n "$comments" ]; then
                local comment_count=$(echo "$comments" | wc -l)
                echo "      Adding $comment_count comments..."
                
                echo "$comments" | while read -r comment_json; do
                    if [ -n "$comment_json" ]; then
                        local comment_body=$(echo "$comment_json" | jq -r '.body')
                        local comment_author=$(echo "$comment_json" | jq -r '.author.login')
                        local comment_date=$(echo "$comment_json" | jq -r '.createdAt')
                        
                        local formatted_comment="$comment_body

---
*Originally posted by @$comment_author on $comment_date*
*Migrated from $SOURCE_ORG/$repo_name*"
                        
                        # Wait for rate limit
                        wait_for_rate_limit "comment"
                        
                        # Add the comment
                        if gh issue comment "$issue_number" --repo "$TARGET_ORG/$repo_name" --body "$formatted_comment" >/dev/null 2>&1; then
                            COMMENTS_PER_MINUTE=$((COMMENTS_PER_MINUTE + 1))
                            COMMENTS_THIS_HOUR=$((COMMENTS_THIS_HOUR + 1))
                            echo -n "."
                        else
                            echo -n "E"
                        fi
                    fi
                done
                echo ""
            fi
            
            # Close issue if needed
            if [ "$state" = "CLOSED" ]; then
                wait_for_rate_limit "issue"
                gh issue close "$issue_number" --repo "$TARGET_ORG/$repo_name" >/dev/null 2>&1
                ISSUES_PER_MINUTE=$((ISSUES_PER_MINUTE + 1))
                ISSUES_THIS_HOUR=$((ISSUES_THIS_HOUR + 1))
                echo "      ✓ Closed issue #$issue_number"
            fi
        else
            echo "      ✗ Failed to create issue"
        fi
        done
    fi
}

# Function to create pull requests (note: GitHub API doesn't allow creating historical PRs)
create_pull_requests() {
    local repo_name=$1
    
    echo "  Checking pull requests for $repo_name..."
    
    if [ ! -f "$PULLS_DIR/${repo_name}_pull_requests.json" ]; then
        echo "    No pull requests file found"
        return 0
    fi
    
    # Handle both GraphQL structure and empty array
    local pr_count
    if [ "$(jq 'type' "$PULLS_DIR/${repo_name}_pull_requests.json")" = '"array"' ]; then
        pr_count=$(jq 'length' "$PULLS_DIR/${repo_name}_pull_requests.json")
    else
        pr_count=$(jq '.data.repository.pullRequests.nodes | length' "$PULLS_DIR/${repo_name}_pull_requests.json")
    fi
    
    if [ "$pr_count" -eq 0 ]; then
        echo "    No pull requests to recreate"
        return 0
    fi
    
    echo "    Found $pr_count pull requests (will be documented as issues)"
    
    # Since we can't recreate PRs exactly, create issues documenting them
    if [ "$(jq 'type' "$PULLS_DIR/${repo_name}_pull_requests.json")" = '"array"' ]; then
        # Empty array, no PRs to process
        return 0
    else
        jq -c '.data.repository.pullRequests.nodes[]' "$PULLS_DIR/${repo_name}_pull_requests.json" | while read -r pr_json; do
        local title=$(echo "$pr_json" | jq -r '.title')
        local body=$(echo "$pr_json" | jq -r '.body // ""')
        local state=$(echo "$pr_json" | jq -r '.state')
        local number=$(echo "$pr_json" | jq -r '.number')
        
        local pr_issue_body="**This was originally Pull Request #$number from $SOURCE_ORG/$repo_name**

$body

---
*Original PR state: $state*
*Migrated from $SOURCE_ORG to $TARGET_ORG*
*Note: This is a documentation of the original pull request, not a recreated PR*"
        
        echo "    Creating documentation issue for PR #$number: $title"
        
        wait_for_rate_limit "issue"
        
        # Create issue to document the PR
        local issue_url=$(gh issue create --repo "$TARGET_ORG/$repo_name" --title "[PR] $title" --body "$pr_issue_body" 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            ISSUES_PER_MINUTE=$((ISSUES_PER_MINUTE + 1))
            ISSUES_THIS_HOUR=$((ISSUES_THIS_HOUR + 1))
            
            local issue_number=$(echo "$issue_url" | sed 's/.*\///')
            echo "      ✓ Created documentation issue #$issue_number"
            
            # Close immediately since it's just documentation
            wait_for_rate_limit "issue"
            gh issue close "$issue_number" --repo "$TARGET_ORG/$repo_name" >/dev/null 2>&1
            ISSUES_PER_MINUTE=$((ISSUES_PER_MINUTE + 1))
            ISSUES_THIS_HOUR=$((ISSUES_THIS_HOUR + 1))
            echo "      ✓ Closed documentation issue #$issue_number"
        else
            echo "      ✗ Failed to create documentation issue"
        fi
        done
    fi
}

# Main migration function
migrate_repository() {
    local repo_name=$1
    
    echo ""
    echo "======================================="
    echo "MIGRATING: $repo_name"
    echo "Time: $(date)"
    echo "Rate limits - Issues: $ISSUES_PER_MINUTE/min ($ISSUES_THIS_HOUR/hour), Comments: $COMMENTS_PER_MINUTE/min ($COMMENTS_THIS_HOUR/hour)"
    echo "======================================="
    
    # Log to file
    echo "$(date): Starting migration of $repo_name" >> "$LOG_FILE"
    
    # Create repository
    create_repository "$repo_name"
    repo_create_result=$?
    
    if [ $repo_create_result -eq 0 ]; then
        echo "$(date): Repository $repo_name created successfully" >> "$LOG_FILE"
    elif [ $repo_create_result -eq 2 ]; then
        echo "$(date): Repository $repo_name already exists, continuing with issues/PRs" >> "$LOG_FILE"
    else
        echo "✗ FAILED: $repo_name"
        echo "$(date): Failed migration of $repo_name" >> "$LOG_FILE"
        return 1
    fi
    
    # Create issues (whether repo was created or already existed)
    create_issues "$repo_name"
    echo "$(date): Issues processed for $repo_name" >> "$LOG_FILE"
    
    # Create pull request documentation
    create_pull_requests "$repo_name"
    echo "$(date): Pull requests processed for $repo_name" >> "$LOG_FILE"
    
    echo ""
    echo "✓ COMPLETED: $repo_name"
    echo "  View at: https://github.com/$TARGET_ORG/$repo_name"
    echo "$(date): Completed migration of $repo_name" >> "$LOG_FILE"
    
    return 0
}

# Main execution
echo "Starting comprehensive migration with rate limiting..."
echo "$(date): Starting comprehensive migration" > "$LOG_FILE"

# Initialize rate limiting
MINUTE_START=$(date +%s)
HOUR_START=$(date +%s)

for repo in "${SORTED_REPOS[@]}"; do
    # Check if repository already exists and skip entirely if it does
    if gh repo view "$TARGET_ORG/$repo" >/dev/null 2>&1; then
        echo ""
        echo "======================================="
        echo "SKIPPING: $repo (already exists)"
        echo "Time: $(date)"
        echo "======================================="
        echo "✓ SKIPPED: $repo - Repository already exists at https://github.com/$TARGET_ORG/$repo"
        echo "$(date): Skipped $repo - already exists" >> "$LOG_FILE"
        continue
    fi
    
    migrate_repository "$repo"
    
    echo ""
    echo "======== MIGRATION PROGRESS ========"
    echo "Rate limits - Issues: $ISSUES_PER_MINUTE/min ($ISSUES_THIS_HOUR/hour)"
    echo "Rate limits - Comments: $COMMENTS_PER_MINUTE/min ($COMMENTS_THIS_HOUR/hour)"
    echo "===================================="
    
    # Brief pause between repositories to avoid overwhelming the API
    echo "Continuing to next repository in 3 seconds..."
    sleep 3
done

echo ""
echo "======================================="
echo "MIGRATION COMPLETED!"
echo "Source: $SOURCE_ORG"
echo "Target: $TARGET_ORG"
echo "All repositories have been migrated to $TARGET_ORG"
echo "$(date): All migrations completed" >> "$LOG_FILE"
echo "======================================="
echo ""
echo "View migrated repositories at: https://github.com/$TARGET_ORG"
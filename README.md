# GitHub Organization Migration Tools

A collection of bash scripts to backup and migrate entire GitHub organizations, including repositories, issues, comments, and pull requests.

## Features

- ✅ **Complete Backup**: Clones all repositories with full git history
- ✅ **Issue Migration**: Exports and recreates all issues with comments
- ⚠️ **Pull Request Documentation**: Documents PRs as special issues (partial migration)
- ✅ **Rate Limit Compliance**: Respects GitHub API limits (20/min, 150/hour)
- ✅ **Proper Attribution**: Preserves original authors and timestamps

## Requirements

- [GitHub CLI](https://cli.github.com/) (`gh`)
- `jq` for JSON processing
- `bash` shell
- Authenticated GitHub account with access to both organizations

## Quick Start

### Complete Migration (Recommended)
```bash
# Backup source org and migrate to target org in one step
./scripts/migrate_organization.sh source-org target-org /path/to/backup
```

### Step-by-Step Migration
```bash
# 1. Backup source organization
./scripts/backup_all.sh source-org /path/to/backup

# 2. Migrate to target organization
./scripts/migrate_with_rate_limits.sh source-org target-org /path/to/backup
```

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `migrate_organization.sh` | **Complete migration** (backup + migrate) |
| `backup_all.sh` | Backup entire organization |
| `migrate_with_rate_limits.sh` | Migrate from backup to target org |
| `clone_repositories.sh` | Clone all repositories |
| `export_issues.sh` | Export all issues and comments |
| `export_pull_requests.sh` | Export all pull requests |

## Examples

```bash
# Migrate powerscope to thalora-dev
./scripts/migrate_organization.sh powerscope thalora-dev ./backup

# Backup powerscope organization
./scripts/backup_all.sh powerscope ./powerscope-backup
```

## Backup Structure

```
backup-directory/
├── repositories/          # Cloned git repositories
│   ├── repo1/
│   ├── repo2/
│   └── ...
├── issues/               # Exported issues as JSON
│   ├── repo1_issues.json
│   ├── repo2_issues.json
│   └── ...
├── pull-requests/        # Exported PRs as JSON
│   ├── repo1_pull_requests.json
│   ├── repo2_pull_requests.json
│   └── ...
└── migration_log.txt    # Migration progress log
```

## Rate Limits

The scripts automatically handle GitHub API rate limits:
- **Issues/Comments**: 20 per minute, 150 per hour
- **Repositories**: No specific limits (git operations)
- **Automatic delays**: Built-in waiting when approaching limits

## Limitations

- **Pull Requests**: Cannot be recreated exactly due to GitHub API limitations. They are documented as special issues instead.
- **Repository Settings**: Webhooks, secrets, and advanced settings are not migrated.
- **Large Files**: LFS files are supported but may require additional time.

## Authentication

Ensure GitHub CLI is authenticated:
```bash
gh auth login
gh auth status
```

The authenticated user must have:
- Read access to source organization
- Admin access to target organization (to create repositories)

## Troubleshooting

### Rate Limit Errors
- Scripts automatically handle rate limits with delays
- If errors persist, check your GitHub API quota: `gh api rate_limit`

### Missing Repositories
- Verify authentication: `gh auth status`
- Check organization access: `gh repo list source-org`

### Permission Errors
- Ensure target organization exists
- Verify admin permissions on target organization

## License

MIT License - Feel free to use and modify these scripts for your needs.
# GitHub Organization Migration Tool

I needed to copy all of my repos, issues & PRs from one organisation to another, so I got Claude to create a `Python` library to do this for me using the `GitHub` API.

> [!CAUTION]
> This has been written by `Claude` with minimal supervision by me


## Features

- ✅ **Complete Backup**: Clones all repositories with full git history
- ✅ **Issue Migration**: Exports and recreates all issues with comments
- ⚠️ **Pull Request Documentation**: Documents PRs as special issues (partial migration)
- ✅ **Rate Limit Compliance**: Respects GitHub API limits (20/min, 150/hour)
- ✅ **Proper Attribution**: Preserves original authors and timestamps

## Requirements

- [`python`](https://www.python.org/) 

>[!NOTE]
> If you're into [`Nix`](https://github.com/NixOS/nix), then you'll just need one tool.
> Run ...
> ```sh
> nix develop
> ```
> ... & `Nix` will install the required tools for you by reading `flake.nix`


## Quick Start

> [!NOTE]
> If you use the `GitHub` CLI, you can generate a token with `gh auth token` & replace `$GITHUB_TOKEN` below with `$(gh auth token)`

```bash
# Basic migration
python migrate.py powerscope thalora-dev $GITHUB_TOKEN

# With custom settings
python migrate.py powerscope thalora-dev $GITHUB_TOKEN \
  --state-file ./my_migration.json \
  --issues-per-min 10 \
  --comments-per-min 15
```

## Resume Capability

If migration fails at any point, simply run the same command again:

```bash
python migrate.py powerscope thalora-dev $GITHUB_TOKEN
```

The tool will:
1. Skip completed repositories
2. Skip completed issues within repositories  
3. Resume adding comments from the exact comment that failed

## Testing

```bash
# Run all tests
python run_tests.py

# Tests are designed to run with only standard library
# No pytest, mock, or other dependencies needed
```

## Error Handling

The tool exits immediately on API failures but provides clear error messages and resume instructions. Common failure points:

1. **Rate limits exceeded** - Wait and resume
2. **API token issues** - Check token permissions  
3. **Network issues** - Resume when connection restored
4. **Repository already exists** - Skipped automatically

## Requirements

- Python 3.6+
- GitHub personal access token with appropriate permissions
- No additional packages needed
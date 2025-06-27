#!/usr/bin/env python3
"""GitHub Organization Migration CLI

A clean, resumable GitHub organization migration tool using only Python standard library.

Usage:
    python migrate.py source_org target_org github_token [--state-file=path] [--issues-per-min=20] [--comments-per-min=20] [--no-content]

Examples:
    python migrate.py powerscope thalora-dev $GITHUB_TOKEN --state-file=./migration_state.json
    python migrate.py powerscope thalora-dev $GITHUB_TOKEN --no-content  # Only migrate issues, not code
"""

import sys
import os
import argparse

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from github_migrator.migrator import GitHubMigrator


def main():
    parser = argparse.ArgumentParser(
        description="Migrate GitHub organization with fine-grained resumability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic migration
  python migrate.py powerscope thalora-dev $GITHUB_TOKEN

  # With custom state file and rate limits
  python migrate.py powerscope thalora-dev $GITHUB_TOKEN \\
    --state-file ./my_migration.json \\
    --issues-per-min 10 \\
    --comments-per-min 15

  # Migrate only issues, skip repository content
  python migrate.py powerscope thalora-dev $GITHUB_TOKEN --no-content

Features:
  - Migrates repository content (code, history, branches, tags)
  - Migrates issues with original numbering (creates placeholders for gaps)
  - Migrates comments with proper author attribution
  - Resumes from exactly where it left off (repository, issue, or comment level)
  - Respects GitHub API rate limits
  - Thread-safe state management
  - Comprehensive logging
  - Uses only Python standard library
        """
    )
    
    parser.add_argument('source_org', help='Source GitHub organization name')
    parser.add_argument('target_org', help='Target GitHub organization name')  
    parser.add_argument('github_token', help='GitHub personal access token')
    parser.add_argument('--state-file', default='migration_state.json',
                       help='Path to state file for resumability (default: migration_state.json)')
    parser.add_argument('--issues-per-min', type=int, default=20,
                       help='Issues per minute rate limit (default: 20)')
    parser.add_argument('--comments-per-min', type=int, default=20,
                       help='Comments per minute rate limit (default: 20)')
    parser.add_argument('--no-content', action='store_true',
                       help='Skip repository content migration (only migrate issues)')
    
    args = parser.parse_args()
    
    print("="*60)
    print("GITHUB ORGANIZATION MIGRATION")
    print("="*60)
    print(f"Source:      {args.source_org}")
    print(f"Target:      {args.target_org}")
    print(f"State file:  {args.state_file}")
    print(f"Rate limits: {args.issues_per_min} issues/min, {args.comments_per_min} comments/min")
    print(f"Content:     {'Disabled' if args.no_content else 'Enabled'}")
    print("="*60)
    print()
    
    # Create migrator
    migrator = GitHubMigrator(
        source_org=args.source_org,
        target_org=args.target_org,
        github_token=args.github_token,
        state_file=args.state_file,
        issues_per_minute=args.issues_per_min,
        comments_per_minute=args.comments_per_min,
        migrate_content=not args.no_content
    )
    
    # Run migration
    try:
        success = migrator.migrate_organization()
        
        if success:
            print("\n" + "="*60)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("="*60)
            sys.exit(0)
        else:
            print("\n" + "="*60)
            print("❌ MIGRATION FAILED")
            print("Run the same command again to resume from where it left off.")
            print("="*60)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("⚠️  MIGRATION INTERRUPTED")
        print("Run the same command again to resume from where it left off.")
        print("="*60)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        print("Run the same command again to resume from where it left off.")
        sys.exit(1)


if __name__ == '__main__':
    main()
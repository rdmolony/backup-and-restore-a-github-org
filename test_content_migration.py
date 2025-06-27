#!/usr/bin/env python3
"""Test script to check repository content migration functionality."""

import sys
import os
import tempfile

# Add github_migrator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from github_migrator.migrator import GitHubMigrator

def test_content_migration():
    """Test repository content migration with a small repo."""
    
    print("Testing repository content migration...")
    print("This will test cloning and pushing operations.")
    print()
    
    # You'll need to provide your own test values
    source_org = input("Enter source org (or press Enter to skip): ").strip()
    if not source_org:
        print("Skipping test - no source org provided")
        return
        
    target_org = input("Enter target org: ").strip()
    if not target_org:
        print("Error: target org required")
        return
        
    repo_name = input("Enter a small test repository name: ").strip()
    if not repo_name:
        print("Error: repository name required")
        return
        
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set")
        return
    
    print(f"Testing content migration: {source_org}/{repo_name} -> {target_org}/{repo_name}")
    print()
    
    # Create migrator
    migrator = GitHubMigrator(
        source_org=source_org,
        target_org=target_org,
        github_token=github_token,
        state_file=tempfile.mktemp(suffix='.json'),
        migrate_content=True  # Enable content migration
    )
    
    # Test just the content migration part
    try:
        print("Starting repository content migration test...")
        success = migrator.migrate_repository_content(repo_name)
        
        if success:
            print("✅ Repository content migration test PASSED")
            print(f"Check {target_org}/{repo_name} to verify content was copied")
        else:
            print("❌ Repository content migration test FAILED")
            
    except Exception as e:
        print(f"❌ Repository content migration test FAILED with exception: {e}")

if __name__ == '__main__':
    test_content_migration()
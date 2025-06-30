"""Main migration orchestrator that coordinates the migration process."""

import logging
import os
import tempfile
import subprocess
from typing import List, Dict, Any, Optional
from github_migrator.github_client import GitHubClient, GitHubAPIError
from github_migrator.state_manager import StateManager  
from github_migrator.rate_limiter import RateLimiter


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GitHubMigrator:
    """Orchestrates GitHub organization migration with state management and rate limiting."""
    
    def __init__(self, source_org: str, target_org: str, github_token: str, 
                 state_file: str, issues_per_minute: int = 20, comments_per_minute: int = 20,
                 migrate_content: bool = True):
        """Initialize the migrator."""
        self.source_org = source_org
        self.target_org = target_org
        self.github_token = github_token
        self.migrate_content = migrate_content
        
        self.client = GitHubClient(github_token)
        self.state = StateManager(state_file)
        self.rate_limiter = RateLimiter(issues_per_minute, comments_per_minute)
        
        logger.info(f"Initialized migrator: {source_org} -> {target_org} (content migration: {migrate_content})")
    
    def get_repositories_to_migrate(self) -> List[Dict[str, Any]]:
        """Get list of repositories that need to be migrated."""
        logger.info(f"Getting repositories from {self.source_org}")
        
        try:
            all_repos = self.client.get_repositories(self.source_org)
            
            # Filter out already completed repositories
            repos_to_migrate = []
            for repo in all_repos:
                if not self.state.is_repo_completed(repo["name"]):
                    repos_to_migrate.append(repo)
                else:
                    logger.info(f"Skipping {repo['name']} - already completed")
            
            logger.info(f"Found {len(repos_to_migrate)} repositories to migrate")
            return repos_to_migrate
            
        except GitHubAPIError as e:
            logger.error(f"Failed to get repositories: {e}")
            raise
    
    def migrate_repository(self, repo_name: str) -> bool:
        """Migrate a single repository including issues and comments."""
        logger.info(f"Starting migration of repository: {repo_name}")
        
        # Check if already completed
        if self.state.is_repo_completed(repo_name):
            logger.info(f"Repository {repo_name} already completed, skipping")
            return True
        
        try:
            # Create repository in target organization if it doesn't exist
            logger.info(f"Creating repository {self.target_org}/{repo_name}")
            try:
                self.client.create_repository(
                    self.target_org, 
                    repo_name, 
                    private=True, 
                    description=f"Migrated from {self.source_org}/{repo_name}"
                )
                logger.info(f"Repository {repo_name} created successfully")
            except GitHubAPIError as e:
                if "Repository creation failed" in str(e) or "422" in str(e):
                    logger.info(f"Repository {repo_name} already exists, continuing with migration")
                else:
                    raise e
            
            # Migrate repository content (code, history) first if enabled
            if self.migrate_content:
                logger.info(f"Starting repository content migration for {repo_name}...")
                if not self.migrate_repository_content(repo_name):
                    logger.warning(f"Failed to migrate repository content for {repo_name}, but continuing")
                    # Don't fail the entire migration for content issues
                else:
                    logger.info(f"Repository content migration completed successfully for {repo_name}")
            else:
                logger.info(f"Repository content migration disabled, skipping for {repo_name}")
            
            # Migrate issues after content
            logger.info(f"Getting issues for {repo_name}")
            issues = self.client.get_issues(self.source_org, repo_name)
            logger.info(f"Found {len(issues)} issues to migrate")
            
            if not self.migrate_issues(repo_name, issues):
                return False
            
            # Mark repository as completed
            self.state.mark_repo_completed(repo_name)
            logger.info(f"Repository {repo_name} migration completed")
            return True
            
        except GitHubAPIError as e:
            logger.error(f"Failed to migrate repository {repo_name}: {e}")
            return False
    
    def migrate_issues(self, repo_name: str, issues: List[Dict[str, Any]]) -> bool:
        """Migrate all issues for a repository, maintaining original numbering."""
        if not issues:
            return True
            
        issue_numbers = [issue["number"] for issue in issues]
        logger.info(f"Processing issues: {issue_numbers}")
        
        # Create a mapping of issue numbers to issue data
        issues_by_number = {issue["number"]: issue for issue in issues}
        
        # Find the range of issue numbers to process
        min_issue = min(issue_numbers)
        max_issue = max(issue_numbers)
        
        # Process all numbers in sequence to maintain numbering
        for issue_number in range(min_issue, max_issue + 1):
            # Check if issue already completed
            if self.state.is_issue_completed(repo_name, issue_number):
                logger.info(f"Issue #{issue_number} already completed, skipping")
                continue
            
            if issue_number in issues_by_number:
                # Real issue exists
                issue = issues_by_number[issue_number]
                if not self._migrate_single_issue(repo_name, issue, issue_number):
                    return False
            else:
                # Missing issue - create placeholder
                logger.info(f"Creating placeholder for missing issue #{issue_number}")
                if not self._create_placeholder_issue(repo_name, issue_number):
                    return False
        
        return True
    
    def _migrate_single_issue(self, repo_name: str, issue: Dict[str, Any], issue_number: int) -> bool:
        """Migrate a single issue."""
        logger.info(f"Migrating issue #{issue_number}: {issue['title']}")
        
        try:
            # Wait for rate limit
            self.rate_limiter.wait_if_necessary('issue')
            
            # Create issue in target repository
            created_issue = self.client.create_issue(
                self.target_org,
                repo_name,
                issue["title"],
                self._format_issue_body(issue, repo_name)
            )
            
            self.rate_limiter.record_request('issue')
            target_issue_number = created_issue["number"]
            logger.info(f"Created issue #{target_issue_number}")
            
            # Migrate comments if any
            comments = issue.get("comments", [])
            # Handle case where comments is a count (int) instead of list
            if isinstance(comments, int) and comments > 0:
                # If comments is an int, fetch the actual comments
                logger.info(f"Issue #{issue_number} has {comments} comments, fetching them")
                try:
                    actual_comments = self.client.get_issue_comments(self.source_org, repo_name, issue_number)
                    if actual_comments and not self.migrate_comments(repo_name, issue_number, target_issue_number, actual_comments):
                        return False
                except GitHubAPIError as e:
                    logger.error(f"Failed to fetch comments for issue #{issue_number}: {e}")
                    # Continue without comments rather than failing
            elif isinstance(comments, list) and len(comments) > 0:
                if not self.migrate_comments(repo_name, issue_number, target_issue_number, comments):
                    return False
            
            # Close issue if it was closed in source
            if issue["state"] == "closed":
                self.rate_limiter.wait_if_necessary('issue')
                self.client.close_issue(self.target_org, repo_name, target_issue_number)
                self.rate_limiter.record_request('issue')
                logger.info(f"Closed issue #{target_issue_number}")
            
            # Mark issue as completed
            self.state.mark_issue_completed(repo_name, issue_number)
            return True
            
        except GitHubAPIError as e:
            logger.error(f"Failed to migrate issue #{issue_number}: {e}")
            return False
    
    def _create_placeholder_issue(self, repo_name: str, issue_number: int) -> bool:
        """Create a placeholder issue for missing issue numbers."""
        try:
            # Wait for rate limit
            self.rate_limiter.wait_if_necessary('issue')
            
            # Create placeholder issue
            created_issue = self.client.create_issue(
                self.target_org,
                repo_name,
                f"[PLACEHOLDER] Issue #{issue_number}",
                f"This is a placeholder for missing issue #{issue_number} from {self.source_org}/{repo_name}.\n\n"
                f"The original issue may have been deleted, converted to a pull request, or never existed.\n\n"
                f"---\n*Created during migration to maintain issue numbering*"
            )
            
            self.rate_limiter.record_request('issue')
            target_issue_number = created_issue["number"]
            
            # Immediately close the placeholder
            self.rate_limiter.wait_if_necessary('issue')
            self.client.close_issue(self.target_org, repo_name, target_issue_number)
            self.rate_limiter.record_request('issue')
            
            logger.info(f"Created and closed placeholder issue #{target_issue_number}")
            
            # Mark as completed
            self.state.mark_issue_completed(repo_name, issue_number)
            return True
            
        except GitHubAPIError as e:
            logger.error(f"Failed to create placeholder for issue #{issue_number}: {e}")
            return False
    
    def migrate_repository_content(self, repo_name: str) -> bool:
        """Migrate repository content (code, history) from source to target."""
        logger.info(f"Starting repository content migration for {repo_name}")
        
        # Check if source repository exists and has content
        try:
            # Try to get repository info first
            source_url_check = f"https://api.github.com/repos/{self.source_org}/{repo_name}"
            logger.info(f"Checking if source repository {self.source_org}/{repo_name} exists and has content")
        except Exception as e:
            logger.warning(f"Could not verify source repository: {e}")
        
        # Create temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = os.path.join(temp_dir, repo_name)
            
            try:
                # Clone source repository
                source_url = f"https://{self.github_token}@github.com/{self.source_org}/{repo_name}.git"
                logger.info(f"Cloning source repository {self.source_org}/{repo_name} (this may take a while for large repos)")
                
                result = subprocess.run([
                    'git', 'clone', '--mirror', source_url, repo_dir
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    logger.error(f"Failed to clone source repository: {result.stderr}")
                    return False
                
                # Change to repository directory
                original_dir = os.getcwd()
                os.chdir(repo_dir)
                
                try:
                    # Add target repository as remote
                    target_url = f"https://{self.github_token}@github.com/{self.target_org}/{repo_name}.git"
                    logger.info(f"Adding target remote {self.target_org}/{repo_name}")
                    
                    result = subprocess.run([
                        'git', 'remote', 'add', 'target', target_url
                    ], capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        logger.error(f"Failed to add target remote: {result.stderr}")
                        return False
                    
                    # Check if Git LFS is configured and install if needed
                    if os.path.exists('.gitattributes'):
                        logger.info("Git LFS configuration detected, ensuring LFS is installed...")
                        subprocess.run(['git', 'lfs', 'install'], capture_output=True, text=True)
                    
                    # Push all branches and tags to target
                    logger.info(f"Pushing all content to target repository {self.target_org}/{repo_name} (this may take a while)")
                    
                    # Push all refs (branches, tags, etc.)
                    result = subprocess.run([
                        'git', 'push', 'target', '--mirror'
                    ], capture_output=True, text=True, timeout=600)
                    
                    if result.returncode != 0:
                        logger.error(f"Failed to push to target repository: {result.stderr}")
                        return False
                    
                    logger.info(f"Repository content migration completed for {repo_name}")
                    return True
                    
                finally:
                    # Always return to original directory
                    os.chdir(original_dir)
                    
            except subprocess.TimeoutExpired:
                logger.error(f"Repository content migration timed out for {repo_name}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error during repository content migration: {e}")
                return False
    
    def _run_git_command(self, args: List[str], cwd: str = None, timeout: int = 300) -> tuple[bool, str]:
        """Helper method to run git commands with proper error handling."""
        try:
            result = subprocess.run(
                ['git'] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def migrate_comments(self, repo_name: str, source_issue_number: int, 
                        target_issue_number: int, comments: List[Dict[str, Any]]) -> bool:
        """Migrate comments for an issue, supporting resume from partial completion."""
        comments_completed = self.state.get_comment_progress(repo_name, source_issue_number)
        
        logger.info(f"Migrating {len(comments)} comments for issue #{source_issue_number} "
                   f"(starting from comment {comments_completed + 1})")
        
        for i, comment in enumerate(comments):
            # Skip already completed comments
            if i < comments_completed:
                continue
            
            try:
                # Wait for rate limit
                self.rate_limiter.wait_if_necessary('comment')
                
                # Create comment
                formatted_comment = self._format_comment_body(comment, repo_name)
                self.client.create_issue_comment(
                    self.target_org,
                    repo_name,
                    target_issue_number,
                    formatted_comment
                )
                
                self.rate_limiter.record_request('comment')
                
                # Update progress
                self.state.update_comment_progress(repo_name, source_issue_number, i + 1)
                logger.info(f"Created comment {i + 1}/{len(comments)}")
                
            except GitHubAPIError as e:
                logger.error(f"Failed to create comment {i + 1} for issue #{source_issue_number}: {e}")
                return False
        
        return True
    
    def migrate_organization(self) -> bool:
        """Migrate entire organization."""
        logger.info(f"Starting organization migration: {self.source_org} -> {self.target_org}")
        
        try:
            repos_to_migrate = self.get_repositories_to_migrate()
            
            for i, repo in enumerate(repos_to_migrate, 1):
                repo_name = repo["name"]
                logger.info(f"[{i}/{len(repos_to_migrate)}] Processing {repo_name}")
                
                if not self.migrate_repository(repo_name):
                    logger.error(f"Migration failed at repository {repo_name}")
                    return False
                
                # Show progress
                stats = self.rate_limiter.get_stats()
                logger.info(f"Progress: {i}/{len(repos_to_migrate)} repos complete. "
                           f"Rate limits: {stats['issues_this_minute']}/{stats['issues_limit']} issues, "
                           f"{stats['comments_this_minute']}/{stats['comments_limit']} comments")
            
            logger.info("Organization migration completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Organization migration failed: {e}")
            return False
    
    def _format_issue_body(self, issue: Dict[str, Any], repo_name: str) -> str:
        """Format issue body with migration metadata."""
        original_body = issue.get("body", "")
        author = issue.get("user", {}).get("login", "unknown")
        created_at = issue.get("created_at", "unknown")
        
        formatted_body = original_body if original_body else "*No description provided*"
        formatted_body += f"\n\n---\n*Originally created by @{author} on {created_at}*\n"
        formatted_body += f"*Migrated from {self.source_org}/{repo_name}*"
        
        return formatted_body
    
    def _format_comment_body(self, comment: Dict[str, Any], repo_name: str) -> str:
        """Format comment body with migration metadata."""
        original_body = comment.get("body", "")
        author = comment.get("user", {}).get("login", "unknown")
        created_at = comment.get("created_at", "unknown")
        
        formatted_body = original_body if original_body else "*No comment text*"
        formatted_body += f"\n\n---\n*Originally posted by @{author} on {created_at}*\n"
        formatted_body += f"*Migrated from {self.source_org}/{repo_name}*"
        
        return formatted_body
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from github_migrator.migrator import GitHubMigrator
from github_migrator.github_client import GitHubAPIError


class TestGitHubMigrator(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_state_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_state_file.close()
        
        self.mock_client = Mock()
        
        # Create migrator with mocked dependencies
        with patch('github_migrator.migrator.GitHubClient') as mock_client_class:
            with patch('github_migrator.migrator.StateManager') as mock_state_class:
                with patch('github_migrator.migrator.RateLimiter') as mock_limiter_class:
                    mock_client_class.return_value = self.mock_client
                    self.mock_state = Mock()
                    mock_state_class.return_value = self.mock_state
                    self.mock_limiter = Mock()
                    mock_limiter_class.return_value = self.mock_limiter
                    
                    self.migrator = GitHubMigrator(
                        source_org="source_org",
                        target_org="target_org", 
                        github_token="test_token",
                        state_file=self.temp_state_file.name
                    )
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_state_file.name):
            os.unlink(self.temp_state_file.name)
    
    def test_initialization(self):
        """Test migrator initialization."""
        self.assertEqual(self.migrator.source_org, "source_org")
        self.assertEqual(self.migrator.target_org, "target_org")
        self.assertIsNotNone(self.migrator.client)
        self.assertIsNotNone(self.migrator.state)
        self.assertIsNotNone(self.migrator.rate_limiter)
    
    def test_get_repositories_to_migrate(self):
        """Test getting list of repositories to migrate."""
        # Mock repository list
        self.mock_client.get_repositories.return_value = [
            {"name": "repo1", "private": True},
            {"name": "repo2", "private": False},
            {"name": "repo3", "private": True}
        ]
        
        # Mock some repos as already completed
        self.mock_state.is_repo_completed.side_effect = lambda name: name == "repo2"
        
        repos = self.migrator.get_repositories_to_migrate()
        
        # Should only return non-completed repos
        self.assertEqual(len(repos), 2)
        self.assertEqual([r["name"] for r in repos], ["repo1", "repo3"])
    
    def test_migrate_repository_already_completed(self):
        """Test skipping already completed repository."""
        self.mock_state.is_repo_completed.return_value = True
        
        result = self.migrator.migrate_repository("test_repo")
        
        self.assertTrue(result)
        self.mock_client.create_repository.assert_not_called()
    
    def test_migrate_repository_success(self):
        """Test successful repository migration."""
        # Setup mocks
        self.mock_state.is_repo_completed.return_value = False
        self.mock_client.create_repository.return_value = {"name": "test_repo"}
        self.mock_client.get_issues.return_value = []
        
        result = self.migrator.migrate_repository("test_repo")
        
        self.assertTrue(result)
        self.mock_client.create_repository.assert_called_once()
        self.mock_state.mark_repo_completed.assert_called_once_with("test_repo")
    
    def test_migrate_repository_api_error(self):
        """Test handling API errors during repository migration."""
        self.mock_state.is_repo_completed.return_value = False
        self.mock_client.create_repository.side_effect = GitHubAPIError("API Error")
        
        result = self.migrator.migrate_repository("test_repo")
        
        self.assertFalse(result)
        self.mock_state.mark_repo_completed.assert_not_called()
    
    def test_migrate_repository_already_exists(self):
        """Test handling repository that already exists (422 error)."""
        self.mock_state.is_repo_completed.return_value = False
        self.mock_client.create_repository.side_effect = GitHubAPIError("GitHub API error 422: Unprocessable Entity - Repository creation failed.")
        self.mock_client.get_issues.return_value = []
        
        result = self.migrator.migrate_repository("test_repo")
        
        # Should succeed even if repo already exists
        self.assertTrue(result)
        self.mock_state.mark_repo_completed.assert_called_once_with("test_repo")
    
    def test_migrate_issues_skip_completed(self):
        """Test skipping already completed issues."""
        issues = [
            {"number": 1, "title": "Issue 1", "state": "open", "body": "Test", "comments": []},
            {"number": 2, "title": "Issue 2", "state": "closed", "body": "Test", "comments": []}
        ]
        
        # Mock issue 1 as completed
        self.mock_state.is_issue_completed.side_effect = lambda repo, num: num == 1
        
        # Mock issue creation return value
        self.mock_client.create_issue.return_value = {"number": 456}
        self.mock_state.get_comment_progress.return_value = 0
        
        result = self.migrator.migrate_issues("test_repo", issues)
        
        self.assertTrue(result)
        # Should only create issue 2
        self.mock_client.create_issue.assert_called_once()
        call_args = self.mock_client.create_issue.call_args
        self.assertEqual(call_args[0][2], "Issue 2")  # title argument
    
    def test_migrate_comments_with_resume(self):
        """Test resuming comment migration from specific point."""
        comments = [
            {"body": "Comment 1", "user": {"login": "user1"}, "created_at": "2023-01-01"},
            {"body": "Comment 2", "user": {"login": "user2"}, "created_at": "2023-01-02"},
            {"body": "Comment 3", "user": {"login": "user3"}, "created_at": "2023-01-03"}
        ]
        
        # Mock 2 comments already completed
        self.mock_state.get_comment_progress.return_value = 2
        self.mock_client.create_issue_comment.return_value = {"id": 1}
        
        result = self.migrator.migrate_comments("test_repo", 1, 123, comments)
        
        self.assertTrue(result)
        # Should only create the 3rd comment (index 2)
        self.mock_client.create_issue_comment.assert_called_once()
        call_args = self.mock_client.create_issue_comment.call_args
        # Check the body argument (which is the 4th positional argument)
        self.assertIn("Comment 3", call_args[0][3])  # body is 4th positional argument
    
    def test_full_migration_process(self):
        """Test full migration process integration."""
        # Mock repositories
        self.mock_client.get_repositories.return_value = [
            {"name": "repo1", "private": True}
        ]
        self.mock_state.is_repo_completed.return_value = False
        
        # Mock repository creation
        self.mock_client.create_repository.return_value = {"name": "repo1"}
        
        # Mock issues
        self.mock_client.get_issues.return_value = [
            {"number": 1, "title": "Test Issue", "state": "open", "body": "Test", "comments": []}
        ]
        self.mock_state.is_issue_completed.return_value = False
        
        # Mock issue creation
        self.mock_client.create_issue.return_value = {"number": 123}
        self.mock_state.get_comment_progress.return_value = 0
        
        # Mock rate limiter stats
        self.mock_limiter.get_stats.return_value = {
            'issues_this_minute': 1,
            'comments_this_minute': 0,
            'issues_limit': 20,
            'comments_limit': 20
        }
        
        result = self.migrator.migrate_organization()
        
        self.assertTrue(result)
        self.mock_client.get_repositories.assert_called_once()
        self.mock_client.create_repository.assert_called_once()
        self.mock_client.get_issues.assert_called_once()
        self.mock_client.create_issue.assert_called_once()
    
    def test_migrate_issues_with_comment_count_instead_of_list(self):
        """Test handling issue where comments is an int (comment count) instead of list."""
        issues = [
            {
                "number": 1, 
                "title": "Issue with comment count", 
                "state": "open", 
                "body": "Test", 
                "comments": 5  # This should be a list but is an int (comment count)
            }
        ]
        
        self.mock_state.is_issue_completed.return_value = False
        self.mock_client.create_issue.return_value = {"number": 123}
        self.mock_client.get_issue_comments.return_value = [
            {"body": "Comment 1", "user": {"login": "user1"}, "created_at": "2023-01-01"},
            {"body": "Comment 2", "user": {"login": "user2"}, "created_at": "2023-01-02"}
        ]
        self.mock_state.get_comment_progress.return_value = 0
        
        # Should now handle the comment count properly
        result = self.migrator.migrate_issues("test_repo", issues)
        
        self.assertTrue(result)
        self.mock_client.create_issue.assert_called_once()
        self.mock_client.get_issue_comments.assert_called_once_with("source_org", "test_repo", 1)
    
    def test_migrate_issues_with_gaps_creates_placeholders(self):
        """Test that missing issue numbers get placeholder issues to maintain numbering."""
        issues = [
            {"number": 1, "title": "Issue 1", "state": "open", "body": "Test", "comments": []},
            {"number": 3, "title": "Issue 3", "state": "open", "body": "Test", "comments": []},
            {"number": 6, "title": "Issue 6", "state": "open", "body": "Test", "comments": []}
        ]
        
        self.mock_state.is_issue_completed.return_value = False
        self.mock_client.create_issue.return_value = {"number": 123}
        
        result = self.migrator.migrate_issues("test_repo", issues)
        
        self.assertTrue(result)
        # Should create 6 issues total: 3 real + 3 placeholders (2, 4, 5)
        self.assertEqual(self.mock_client.create_issue.call_count, 6)
        
        # Check that placeholders were created
        create_calls = self.mock_client.create_issue.call_args_list
        placeholder_titles = [call[0][2] for call in create_calls if "[PLACEHOLDER]" in call[0][2]]
        self.assertEqual(len(placeholder_titles), 3)  # Issues 2, 4, 5
        self.assertIn("[PLACEHOLDER] Issue #2", placeholder_titles)
        self.assertIn("[PLACEHOLDER] Issue #4", placeholder_titles)
        self.assertIn("[PLACEHOLDER] Issue #5", placeholder_titles)
    
    def test_migrate_issues_processes_in_order(self):
        """Test that issues are processed in numerical order regardless of input order."""
        # Issues provided out of order
        issues = [
            {"number": 5, "title": "Issue 5", "state": "open", "body": "Test", "comments": []},
            {"number": 2, "title": "Issue 2", "state": "open", "body": "Test", "comments": []},
            {"number": 8, "title": "Issue 8", "state": "open", "body": "Test", "comments": []}
        ]
        
        self.mock_state.is_issue_completed.return_value = False
        self.mock_client.create_issue.return_value = {"number": 123}
        
        result = self.migrator.migrate_issues("test_repo", issues)
        
        self.assertTrue(result)
        # Should create 7 issues total (2,3,4,5,6,7,8) - 3 real + 4 placeholders
        self.assertEqual(self.mock_client.create_issue.call_count, 7)
        
        # Verify issues were processed in order by checking call sequence
        create_calls = self.mock_client.create_issue.call_args_list
        titles = [call[0][2] for call in create_calls]
        
        # Should be in order: Issue 2, [PLACEHOLDER] Issue #3, [PLACEHOLDER] Issue #4, Issue 5, etc.
        self.assertEqual(titles[0], "Issue 2")
        self.assertEqual(titles[1], "[PLACEHOLDER] Issue #3")
        self.assertEqual(titles[2], "[PLACEHOLDER] Issue #4")
        self.assertEqual(titles[3], "Issue 5")
    
    def test_create_placeholder_issue(self):
        """Test creating placeholder issues for missing numbers."""
        self.mock_client.create_issue.return_value = {"number": 123}
        
        result = self.migrator._create_placeholder_issue("test_repo", 42)
        
        self.assertTrue(result)
        self.mock_client.create_issue.assert_called_once()
        call_args = self.mock_client.create_issue.call_args
        self.assertEqual(call_args[0][2], "[PLACEHOLDER] Issue #42")  # title
        self.assertIn("placeholder for missing issue #42", call_args[0][3])  # body
        
        # Should close the placeholder immediately
        self.mock_client.close_issue.assert_called_once_with("target_org", "test_repo", 123)
        self.mock_state.mark_issue_completed.assert_called_once_with("test_repo", 42)
    
    def test_migrate_single_issue_with_comments_as_list(self):
        """Test migrating issue when comments are provided as a list."""
        issue = {
            "number": 1,
            "title": "Test Issue",
            "state": "open",
            "body": "Test body",
            "comments": [
                {"body": "Comment 1", "user": {"login": "user1"}, "created_at": "2023-01-01"}
            ]
        }
        
        self.mock_client.create_issue.return_value = {"number": 123}
        self.mock_state.get_comment_progress.return_value = 0
        
        result = self.migrator._migrate_single_issue("test_repo", issue, 1)
        
        self.assertTrue(result)
        self.mock_client.create_issue.assert_called_once()
        # Should not call get_issue_comments since we have a list
        self.mock_client.get_issue_comments.assert_not_called()
    
    def test_migrate_single_issue_with_comments_as_count(self):
        """Test migrating issue when comments are provided as a count."""
        issue = {
            "number": 1,
            "title": "Test Issue",
            "state": "open",
            "body": "Test body",
            "comments": 3  # Comment count
        }
        
        self.mock_client.create_issue.return_value = {"number": 123}
        self.mock_client.get_issue_comments.return_value = [
            {"body": "Comment 1", "user": {"login": "user1"}, "created_at": "2023-01-01"},
            {"body": "Comment 2", "user": {"login": "user2"}, "created_at": "2023-01-02"},
            {"body": "Comment 3", "user": {"login": "user3"}, "created_at": "2023-01-03"}
        ]
        self.mock_state.get_comment_progress.return_value = 0
        
        result = self.migrator._migrate_single_issue("test_repo", issue, 1)
        
        self.assertTrue(result)
        self.mock_client.create_issue.assert_called_once()
        # Should call get_issue_comments to fetch actual comments
        self.mock_client.get_issue_comments.assert_called_once_with("source_org", "test_repo", 1)
    
    def test_migrate_single_issue_closed_state(self):
        """Test that closed issues are properly closed in target."""
        issue = {
            "number": 1,
            "title": "Closed Issue",
            "state": "closed",
            "body": "Test body",
            "comments": []
        }
        
        self.mock_client.create_issue.return_value = {"number": 123}
        
        result = self.migrator._migrate_single_issue("test_repo", issue, 1)
        
        self.assertTrue(result)
        self.mock_client.create_issue.assert_called_once()
        self.mock_client.close_issue.assert_called_once_with("target_org", "test_repo", 123)
        self.mock_state.mark_issue_completed.assert_called_once_with("test_repo", 1)


if __name__ == '__main__':
    unittest.main()
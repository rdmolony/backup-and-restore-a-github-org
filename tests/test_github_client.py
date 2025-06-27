import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import urllib.error
from github_migrator.github_client import GitHubClient, GitHubAPIError


class TestGitHubClient(unittest.TestCase):
    
    def setUp(self):
        self.client = GitHubClient(token="test_token")
    
    def test_initialization_sets_token(self):
        """Test that client stores the token correctly."""
        self.assertEqual(self.client.token, "test_token")
    
    @patch('urllib.request.urlopen')
    def test_get_repositories_success(self, mock_urlopen):
        """Test successful repository listing."""
        # Mock response
        mock_response = Mock()
        mock_response.read.return_value = json.dumps([
            {"name": "repo1", "private": True},
            {"name": "repo2", "private": False}
        ]).encode('utf-8')
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        repos = self.client.get_repositories("test_org")
        
        self.assertEqual(len(repos), 2)
        self.assertEqual(repos[0]["name"], "repo1")
        self.assertEqual(repos[1]["name"], "repo2")
    
    @patch('urllib.request.urlopen')
    def test_get_repositories_api_error(self, mock_urlopen):
        """Test API error handling."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="test", code=403, msg="Forbidden", hdrs=None, fp=None
        )
        
        with self.assertRaises(GitHubAPIError) as context:
            self.client.get_repositories("test_org")
        
        self.assertIn("403", str(context.exception))
    
    @patch('urllib.request.urlopen')
    def test_create_repository_success(self, mock_urlopen):
        """Test successful repository creation."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "name": "new_repo",
            "html_url": "https://github.com/test_org/new_repo"
        }).encode('utf-8')
        mock_response.getcode.return_value = 201
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.client.create_repository("test_org", "new_repo", private=True)
        
        self.assertEqual(result["name"], "new_repo")
        self.assertIn("html_url", result)
    
    @patch('urllib.request.urlopen')
    def test_get_issues_success(self, mock_urlopen):
        """Test successful issues retrieval."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps([
            {
                "number": 1,
                "title": "Test Issue",
                "body": "Test body",
                "state": "open"
            }
        ]).encode('utf-8')
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        issues = self.client.get_issues("test_org", "test_repo")
        
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["number"], 1)
        self.assertEqual(issues[0]["title"], "Test Issue")
    
    @patch('urllib.request.urlopen')
    def test_get_issues_sorted_by_number(self, mock_urlopen):
        """Test that issues are returned sorted by number ascending."""
        mock_response = Mock()
        # Return issues in descending order (as GitHub API typically does)
        mock_response.read.return_value = json.dumps([
            {"number": 5, "title": "Issue 5", "body": "Test", "state": "open"},
            {"number": 2, "title": "Issue 2", "body": "Test", "state": "open"},
            {"number": 8, "title": "Issue 8", "body": "Test", "state": "open"},
            {"number": 1, "title": "Issue 1", "body": "Test", "state": "open"}
        ]).encode('utf-8')
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        issues = self.client.get_issues("test_org", "test_repo")
        
        # Should be sorted by number ascending
        self.assertEqual(len(issues), 4)
        self.assertEqual(issues[0]["number"], 1)
        self.assertEqual(issues[1]["number"], 2)
        self.assertEqual(issues[2]["number"], 5)
        self.assertEqual(issues[3]["number"], 8)
    
    @patch('urllib.request.urlopen')
    def test_get_issues_with_sort_parameters(self, mock_urlopen):
        """Test that get_issues includes proper sort parameters."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps([]).encode('utf-8')
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        self.client.get_issues("test_org", "test_repo")
        
        # Check that the URL includes sort parameters
        call_args = mock_urlopen.call_args
        url = call_args[0][0].full_url
        self.assertIn("sort=created", url)
        self.assertIn("direction=asc", url)
        self.assertIn("per_page=100", url)
    
    @patch('urllib.request.urlopen')
    def test_get_issue_comments_success(self, mock_urlopen):
        """Test successful issue comments retrieval."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps([
            {
                "id": 1,
                "body": "First comment",
                "user": {"login": "user1"},
                "created_at": "2023-01-01T00:00:00Z"
            },
            {
                "id": 2,
                "body": "Second comment",
                "user": {"login": "user2"},
                "created_at": "2023-01-02T00:00:00Z"
            }
        ]).encode('utf-8')
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        comments = self.client.get_issue_comments("test_org", "test_repo", 123)
        
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["body"], "First comment")
        self.assertEqual(comments[0]["user"]["login"], "user1")
        self.assertEqual(comments[1]["body"], "Second comment")
        self.assertEqual(comments[1]["user"]["login"], "user2")
    
    @patch('urllib.request.urlopen')
    def test_create_issue_comment_success(self, mock_urlopen):
        """Test successful issue comment creation."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "id": 123,
            "body": "New comment",
            "html_url": "https://github.com/test_org/test_repo/issues/1#issuecomment-123"
        }).encode('utf-8')
        mock_response.getcode.return_value = 201
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.client.create_issue_comment("test_org", "test_repo", 1, "New comment")
        
        self.assertEqual(result["id"], 123)
        self.assertEqual(result["body"], "New comment")
        self.assertIn("html_url", result)
    
    @patch('urllib.request.urlopen') 
    def test_close_issue_success(self, mock_urlopen):
        """Test successful issue closing."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            "number": 1,
            "state": "closed",
            "title": "Test Issue"
        }).encode('utf-8')
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.client.close_issue("test_org", "test_repo", 1)
        
        self.assertEqual(result["number"], 1)
        self.assertEqual(result["state"], "closed")


if __name__ == '__main__':
    unittest.main()
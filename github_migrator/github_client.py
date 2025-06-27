"""GitHub API client using only standard library."""

import urllib.request
import urllib.error
import urllib.parse
import json
from typing import Dict, List, Any, Optional


class GitHubAPIError(Exception):
    """Custom exception for GitHub API errors."""
    pass


class GitHubClient:
    """GitHub API client using urllib from standard library."""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: str):
        """Initialize client with GitHub token."""
        self.token = token
    
    def _make_request(self, url: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to GitHub API."""
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "github-migrator/0.1.0"
        }
        
        # Prepare request data
        request_data = None
        if data is not None:
            request_data = json.dumps(data).encode('utf-8')
            headers["Content-Type"] = "application/json"
        
        # Create request
        req = urllib.request.Request(url, data=request_data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode('utf-8')
                return json.loads(response_data)
        except urllib.error.HTTPError as e:
            error_msg = f"GitHub API error {e.code}: {e.reason}"
            if hasattr(e, 'read'):
                try:
                    error_body = json.loads(e.read().decode('utf-8'))
                    if 'message' in error_body:
                        error_msg += f" - {error_body['message']}"
                except:
                    pass
            raise GitHubAPIError(error_msg) from e
        except urllib.error.URLError as e:
            raise GitHubAPIError(f"Network error: {e.reason}") from e
    
    def get_repositories(self, org: str) -> List[Dict[str, Any]]:
        """Get all repositories for an organization."""
        url = f"{self.BASE_URL}/orgs/{org}/repos"
        return self._make_request(url)
    
    def create_repository(self, org: str, name: str, private: bool = True, 
                         description: str = None) -> Dict[str, Any]:
        """Create a new repository in the organization."""
        url = f"{self.BASE_URL}/orgs/{org}/repos"
        data = {
            "name": name,
            "private": private
        }
        if description:
            data["description"] = description
        
        return self._make_request(url, method="POST", data=data)
    
    def get_issues(self, org: str, repo: str, state: str = "all") -> List[Dict[str, Any]]:
        """Get all issues for a repository, sorted by issue number ascending."""
        url = f"{self.BASE_URL}/repos/{org}/{repo}/issues"
        params = {"state": state, "per_page": 100, "sort": "created", "direction": "asc"}
        url_with_params = f"{url}?{urllib.parse.urlencode(params)}"
        issues = self._make_request(url_with_params)
        # Sort by issue number to ensure proper order
        return sorted(issues, key=lambda x: x["number"])
    
    def create_issue(self, org: str, repo: str, title: str, body: str = None) -> Dict[str, Any]:
        """Create a new issue."""
        url = f"{self.BASE_URL}/repos/{org}/{repo}/issues"
        data = {"title": title}
        if body:
            data["body"] = body
        
        return self._make_request(url, method="POST", data=data)
    
    def close_issue(self, org: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Close an issue."""
        url = f"{self.BASE_URL}/repos/{org}/{repo}/issues/{issue_number}"
        data = {"state": "closed"}
        return self._make_request(url, method="PATCH", data=data)
    
    def get_issue_comments(self, org: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
        """Get all comments for an issue."""
        url = f"{self.BASE_URL}/repos/{org}/{repo}/issues/{issue_number}/comments"
        params = {"per_page": 100}
        url_with_params = f"{url}?{urllib.parse.urlencode(params)}"
        return self._make_request(url_with_params)
    
    def create_issue_comment(self, org: str, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        url = f"{self.BASE_URL}/repos/{org}/{repo}/issues/{issue_number}/comments"
        data = {"body": body}
        return self._make_request(url, method="POST", data=data)
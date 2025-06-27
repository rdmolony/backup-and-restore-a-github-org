"""State management for GitHub migration using JSON persistence."""

import json
import os
from typing import List, Dict, Any
import threading


class StateManager:
    """Manages migration state with JSON persistence."""
    
    def __init__(self, state_file_path: str):
        """Initialize state manager with file path."""
        self.state_file_path = state_file_path
        self._lock = threading.Lock()
        self._initialize_state_file()
    
    def _initialize_state_file(self):
        """Create initial state file if it doesn't exist."""
        if not os.path.exists(self.state_file_path):
            initial_state = {"repositories": {}}
            self._write_state(initial_state)
    
    def _read_state(self) -> Dict[str, Any]:
        """Read current state from file."""
        try:
            with open(self.state_file_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {"repositories": {}}
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"repositories": {}}
    
    def _write_state(self, state: Dict[str, Any]):
        """Write state to file."""
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _ensure_repo_exists(self, state: Dict[str, Any], repo_name: str):
        """Ensure repository structure exists in state."""
        if repo_name not in state["repositories"]:
            state["repositories"][repo_name] = {
                "completed": False,
                "issues": {}
            }
    
    def _ensure_issue_exists(self, state: Dict[str, Any], repo_name: str, issue_number: int):
        """Ensure issue structure exists in state."""
        self._ensure_repo_exists(state, repo_name)
        issue_key = str(issue_number)
        if issue_key not in state["repositories"][repo_name]["issues"]:
            state["repositories"][repo_name]["issues"][issue_key] = {
                "completed": False,
                "comments_completed": 0
            }
    
    def is_repo_completed(self, repo_name: str) -> bool:
        """Check if repository migration is completed."""
        with self._lock:
            state = self._read_state()
            if repo_name not in state["repositories"]:
                return False
            return state["repositories"][repo_name].get("completed", False)
    
    def mark_repo_completed(self, repo_name: str):
        """Mark repository as completed."""
        with self._lock:
            state = self._read_state()
            self._ensure_repo_exists(state, repo_name)
            state["repositories"][repo_name]["completed"] = True
            self._write_state(state)
    
    def is_issue_completed(self, repo_name: str, issue_number: int) -> bool:
        """Check if issue migration is completed."""
        with self._lock:
            state = self._read_state()
            if repo_name not in state["repositories"]:
                return False
            
            issue_key = str(issue_number)
            if issue_key not in state["repositories"][repo_name]["issues"]:
                return False
            
            return state["repositories"][repo_name]["issues"][issue_key].get("completed", False)
    
    def mark_issue_completed(self, repo_name: str, issue_number: int):
        """Mark issue as completed."""
        with self._lock:
            state = self._read_state()
            self._ensure_issue_exists(state, repo_name, issue_number)
            issue_key = str(issue_number)
            state["repositories"][repo_name]["issues"][issue_key]["completed"] = True
            self._write_state(state)
    
    def get_comment_progress(self, repo_name: str, issue_number: int) -> int:
        """Get number of comments completed for an issue."""
        with self._lock:
            state = self._read_state()
            if repo_name not in state["repositories"]:
                return 0
            
            issue_key = str(issue_number)
            if issue_key not in state["repositories"][repo_name]["issues"]:
                return 0
            
            return state["repositories"][repo_name]["issues"][issue_key].get("comments_completed", 0)
    
    def update_comment_progress(self, repo_name: str, issue_number: int, comments_completed: int):
        """Update number of comments completed for an issue."""
        with self._lock:
            state = self._read_state()
            self._ensure_issue_exists(state, repo_name, issue_number)
            issue_key = str(issue_number)
            state["repositories"][repo_name]["issues"][issue_key]["comments_completed"] = comments_completed
            self._write_state(state)
    
    def get_completed_repositories(self) -> List[str]:
        """Get list of completed repository names."""
        with self._lock:
            state = self._read_state()
            completed = []
            for repo_name, repo_data in state["repositories"].items():
                if repo_data.get("completed", False):
                    completed.append(repo_name)
            return completed
    
    def get_completed_issues(self, repo_name: str) -> List[int]:
        """Get list of completed issue numbers for a repository."""
        with self._lock:
            state = self._read_state()
            if repo_name not in state["repositories"]:
                return []
            
            completed = []
            for issue_key, issue_data in state["repositories"][repo_name]["issues"].items():
                if issue_data.get("completed", False):
                    completed.append(int(issue_key))
            return completed
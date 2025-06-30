import unittest
import tempfile
import os
import json
from github_migrator.state_manager import StateManager


class TestStateManager(unittest.TestCase):
    
    def setUp(self):
        """Create a temporary file for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.state_manager = StateManager(self.temp_file.name)
    
    def tearDown(self):
        """Clean up temporary file."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_initialization_creates_empty_state(self):
        """Test that initialization creates an empty state file."""
        self.assertTrue(os.path.exists(self.temp_file.name))
        
        # Use the state manager's own method to read state
        state = self.state_manager._read_state()
        
        self.assertEqual(state, {"repositories": {}})
    
    def test_is_repo_completed_false_for_new_repo(self):
        """Test that new repositories are not marked as completed."""
        self.assertFalse(self.state_manager.is_repo_completed("test_repo"))
    
    def test_mark_repo_completed(self):
        """Test marking a repository as completed."""
        self.state_manager.mark_repo_completed("test_repo")
        self.assertTrue(self.state_manager.is_repo_completed("test_repo"))
    
    def test_is_issue_completed_false_for_new_issue(self):
        """Test that new issues are not marked as completed."""
        self.assertFalse(self.state_manager.is_issue_completed("test_repo", 1))
    
    def test_mark_issue_completed(self):
        """Test marking an issue as completed."""
        self.state_manager.mark_issue_completed("test_repo", 1)
        self.assertTrue(self.state_manager.is_issue_completed("test_repo", 1))
    
    def test_get_comment_progress_zero_for_new_issue(self):
        """Test that new issues have zero comment progress."""
        progress = self.state_manager.get_comment_progress("test_repo", 1)
        self.assertEqual(progress, 0)
    
    def test_update_comment_progress(self):
        """Test updating comment progress."""
        self.state_manager.update_comment_progress("test_repo", 1, 5)
        progress = self.state_manager.get_comment_progress("test_repo", 1)
        self.assertEqual(progress, 5)
    
    def test_state_persists_across_instances(self):
        """Test that state persists when creating new StateManager instances."""
        # Mark repo as completed in first instance
        self.state_manager.mark_repo_completed("test_repo")
        self.state_manager.update_comment_progress("test_repo", 1, 3)
        
        # Create new instance with same file
        new_state_manager = StateManager(self.temp_file.name)
        
        # Verify state persisted
        self.assertTrue(new_state_manager.is_repo_completed("test_repo"))
        self.assertEqual(new_state_manager.get_comment_progress("test_repo", 1), 3)
    
    def test_content_completion_tracking(self):
        """Test content completion tracking."""
        # Initially not completed
        self.assertFalse(self.state_manager.is_content_completed("test_repo"))
        
        # Mark as completed
        self.state_manager.mark_content_completed("test_repo")
        self.assertTrue(self.state_manager.is_content_completed("test_repo"))
    
    def test_issues_completion_tracking(self):
        """Test issues completion tracking."""
        # Initially not completed
        self.assertFalse(self.state_manager.is_issues_completed("test_repo"))
        
        # Mark as completed
        self.state_manager.mark_issues_completed("test_repo")
        self.assertTrue(self.state_manager.is_issues_completed("test_repo"))
    
    def test_repo_completion_requires_both_content_and_issues(self):
        """Test that repo completion requires both content and issues to be complete."""
        # Initially not completed
        self.assertFalse(self.state_manager.is_repo_completed("test_repo"))
        
        # Only content completed - not fully complete
        self.state_manager.mark_content_completed("test_repo")
        self.assertFalse(self.state_manager.is_repo_completed("test_repo"))
        
        # Only issues completed - not fully complete  
        self.state_manager.mark_issues_completed("test_repo")
        self.assertTrue(self.state_manager.is_repo_completed("test_repo"))
    
    def test_mark_repo_completed_marks_both_parts(self):
        """Test that mark_repo_completed marks both content and issues as complete."""
        self.state_manager.mark_repo_completed("test_repo")
        
        self.assertTrue(self.state_manager.is_content_completed("test_repo"))
        self.assertTrue(self.state_manager.is_issues_completed("test_repo"))
        self.assertTrue(self.state_manager.is_repo_completed("test_repo"))
    
    def test_state_migration_for_existing_repo_with_issues(self):
        """Test state migration for existing repo that has completed issues."""
        # Manually create old-style state with just issues data
        state = self.state_manager._read_state()
        state["repositories"]["old_repo"] = {
            "issues": {
                "1": {"completed": True, "comments_completed": 5},
                "2": {"completed": True, "comments_completed": 0}
            }
        }
        self.state_manager._write_state(state)
        
        # Check that issues completion is inferred from issue data
        self.assertTrue(self.state_manager.is_issues_completed("old_repo"))
        # Check that content completion defaults to False
        self.assertFalse(self.state_manager.is_content_completed("old_repo"))
        
    def test_state_migration_for_existing_repo_with_no_issues(self):
        """Test state migration for existing repo with no issues."""
        # Manually create old-style state with empty issues
        state = self.state_manager._read_state()
        state["repositories"]["empty_repo"] = {"issues": {}}
        self.state_manager._write_state(state)
        
        # Check that issues completion is False (no completed issues)
        self.assertFalse(self.state_manager.is_issues_completed("empty_repo"))
        # Check that content completion defaults to False
        self.assertFalse(self.state_manager.is_content_completed("empty_repo"))
    
    def test_get_completed_repositories(self):
        """Test getting list of completed repositories."""
        self.state_manager.mark_repo_completed("repo1")
        self.state_manager.mark_content_completed("repo2")  # Only content, not complete
        self.state_manager.mark_issues_completed("repo3")   # Only issues, not complete
        
        completed = self.state_manager.get_completed_repositories()
        self.assertEqual(set(completed), {"repo1"})
    
    def test_get_completed_issues(self):
        """Test getting list of completed issues for a repository."""
        self.state_manager.mark_issue_completed("test_repo", 1)
        self.state_manager.mark_issue_completed("test_repo", 3)
        
        completed = self.state_manager.get_completed_issues("test_repo")
        self.assertEqual(set(completed), {1, 3})


if __name__ == '__main__':
    unittest.main()
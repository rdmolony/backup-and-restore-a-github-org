import unittest
from unittest.mock import patch, Mock
import time
from github_migrator.rate_limiter import RateLimiter


class TestRateLimiter(unittest.TestCase):
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(issues_per_minute=20, comments_per_minute=20)
        self.assertEqual(limiter.issues_per_minute, 20)
        self.assertEqual(limiter.comments_per_minute, 20)
    
    @patch('time.time')
    def test_can_make_request_initial(self, mock_time):
        """Test that initial requests are allowed."""
        mock_time.return_value = 1000.0
        limiter = RateLimiter(issues_per_minute=20, comments_per_minute=20)
        
        self.assertTrue(limiter.can_make_request('issue'))
        self.assertTrue(limiter.can_make_request('comment'))
    
    @patch('time.time')
    def test_rate_limit_enforced(self, mock_time):
        """Test that rate limits are enforced."""
        mock_time.return_value = 1000.0
        limiter = RateLimiter(issues_per_minute=2, comments_per_minute=2)
        
        # Make maximum allowed requests
        self.assertTrue(limiter.can_make_request('issue'))
        limiter.record_request('issue')
        self.assertTrue(limiter.can_make_request('issue'))
        limiter.record_request('issue')
        
        # Next request should be blocked
        self.assertFalse(limiter.can_make_request('issue'))
    
    @patch('time.time')
    def test_window_reset(self, mock_time):
        """Test that rate limit window resets after a minute."""
        start_time = 1000.0
        mock_time.return_value = start_time
        limiter = RateLimiter(issues_per_minute=1, comments_per_minute=1)
        
        # Use up the rate limit
        self.assertTrue(limiter.can_make_request('issue'))
        limiter.record_request('issue')
        self.assertFalse(limiter.can_make_request('issue'))
        
        # Move time forward by more than a minute
        mock_time.return_value = start_time + 61
        
        # Should be allowed again
        self.assertTrue(limiter.can_make_request('issue'))
    
    @patch('time.time')
    def test_different_request_types_tracked_separately(self, mock_time):
        """Test that issues and comments are tracked separately."""
        mock_time.return_value = 1000.0
        limiter = RateLimiter(issues_per_minute=1, comments_per_minute=1)
        
        # Use issue limit
        self.assertTrue(limiter.can_make_request('issue'))
        limiter.record_request('issue')
        self.assertFalse(limiter.can_make_request('issue'))
        
        # Comment should still be available
        self.assertTrue(limiter.can_make_request('comment'))
        limiter.record_request('comment')
        self.assertFalse(limiter.can_make_request('comment'))
    
    @patch('time.sleep')
    @patch('time.time')
    def test_wait_if_necessary(self, mock_time, mock_sleep):
        """Test wait_if_necessary method."""
        start_time = 1000.0
        mock_time.return_value = start_time
        limiter = RateLimiter(issues_per_minute=1, comments_per_minute=1)
        
        # Use up the rate limit
        limiter.record_request('issue')
        
        # Set time so we need to wait 30 seconds
        mock_time.return_value = start_time + 30
        
        limiter.wait_if_necessary('issue')
        
        # Should have slept for 30 seconds (60 - 30)
        mock_sleep.assert_called_once_with(30)
    
    @patch('time.sleep')
    @patch('time.time')
    def test_no_wait_when_within_limits(self, mock_time, mock_sleep):
        """Test that no wait occurs when within limits."""
        mock_time.return_value = 1000.0
        limiter = RateLimiter(issues_per_minute=2, comments_per_minute=2)
        
        # Make one request, should not need to wait for the next
        limiter.record_request('issue')
        limiter.wait_if_necessary('issue')
        
        # Should not have slept
        mock_sleep.assert_not_called()
    
    def test_get_stats(self):
        """Test getting rate limit statistics."""
        limiter = RateLimiter(issues_per_minute=20, comments_per_minute=20)
        
        # Make some requests
        limiter.record_request('issue')
        limiter.record_request('issue')
        limiter.record_request('comment')
        
        stats = limiter.get_stats()
        
        self.assertEqual(stats['issues_this_minute'], 2)
        self.assertEqual(stats['comments_this_minute'], 1)
        self.assertEqual(stats['issues_limit'], 20)
        self.assertEqual(stats['comments_limit'], 20)


if __name__ == '__main__':
    unittest.main()
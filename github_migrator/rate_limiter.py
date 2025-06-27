"""Rate limiting for GitHub API requests."""

import time
from typing import Dict, List, Literal
from dataclasses import dataclass, field


@dataclass
class RequestWindow:
    """Tracks requests within a time window."""
    timestamps: List[float] = field(default_factory=list)
    limit: int = 20
    window_seconds: int = 60


class RateLimiter:
    """Rate limiter for GitHub API requests."""
    
    def __init__(self, issues_per_minute: int = 20, comments_per_minute: int = 20):
        """Initialize rate limiter with per-minute limits."""
        self.issues_per_minute = issues_per_minute
        self.comments_per_minute = comments_per_minute
        
        self.windows = {
            'issue': RequestWindow(limit=issues_per_minute),
            'comment': RequestWindow(limit=comments_per_minute)
        }
    
    def _clean_old_requests(self, request_type: Literal['issue', 'comment']):
        """Remove requests older than the window."""
        current_time = time.time()
        window = self.windows[request_type]
        cutoff_time = current_time - window.window_seconds
        
        # Keep only requests within the window
        window.timestamps = [ts for ts in window.timestamps if ts > cutoff_time]
    
    def can_make_request(self, request_type: Literal['issue', 'comment']) -> bool:
        """Check if a request can be made without exceeding rate limits."""
        self._clean_old_requests(request_type)
        window = self.windows[request_type]
        return len(window.timestamps) < window.limit
    
    def record_request(self, request_type: Literal['issue', 'comment']):
        """Record that a request was made."""
        current_time = time.time()
        self.windows[request_type].timestamps.append(current_time)
        self._clean_old_requests(request_type)
    
    def wait_if_necessary(self, request_type: Literal['issue', 'comment']):
        """Wait if necessary to avoid exceeding rate limits."""
        if self.can_make_request(request_type):
            return
        
        # Find the oldest request timestamp
        window = self.windows[request_type]
        if not window.timestamps:
            return
        
        oldest_request = min(window.timestamps)
        current_time = time.time()
        wait_time = window.window_seconds - (current_time - oldest_request)
        
        if wait_time > 0:
            time.sleep(wait_time)
    
    def get_stats(self) -> Dict[str, int]:
        """Get current rate limit statistics."""
        self._clean_old_requests('issue')
        self._clean_old_requests('comment')
        
        return {
            'issues_this_minute': len(self.windows['issue'].timestamps),
            'comments_this_minute': len(self.windows['comment'].timestamps),
            'issues_limit': self.issues_per_minute,
            'comments_limit': self.comments_per_minute
        }
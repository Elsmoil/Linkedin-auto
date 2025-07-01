import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInSessionManager:
    """Manage LinkedIn automation sessions and rate limiting"""
    
    def __init__(self):
        self.session_file = Path("logs/linkedin_session.json")
        self.session_file.parent.mkdir(exist_ok=True)
        self.session_data = self.load_session()
    
    def load_session(self) -> Dict[str, Any]:
        """Load existing session data"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                logger.info("✅ Loaded session data")
                return data
            except Exception as e:
                logger.warning(f"⚠️ Failed to load session: {e}")
        
        return {
            "session_id": f"session_{int(datetime.now().timestamp())}",
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "session_active": False,
            "daily_actions": 0,
            "last_reset": datetime.now().date().isoformat(),
            "rate_limits": {
                "connections": 0,
                "messages": 0,
                "applications": 0,
                "posts": 0
            },
            "daily_limits": {
                "connections": 20,
                "messages": 10,
                "applications": 10,
                "posts": 2
            }
        }
    
    def save_session(self):
        """Save session data to file"""
        try:
            with open(self.session_file, 'w') as f:
                json.dump(self.session_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save session: {e}")
    
    def is_session_valid(self) -> bool:
        """Check if current session is still valid"""
        if not self.session_data.get("last_login"):
            return False
        
        try:
            last_login = datetime.fromisoformat(self.session_data["last_login"])
            return datetime.now() - last_login < timedelta(hours=8)
        except:
            return False
    
    def start_session(self):
        """Start a new session"""
        self.session_data.update({
            "session_id": f"session_{int(datetime.now().timestamp())}",
            "last_login": datetime.now().isoformat(),
            "session_active": True
        })
        self._reset_daily_counters_if_needed()
        self.save_session()
        logger.info(f"🚀 Started new session: {self.session_data['session_id']}")
    
    def end_session(self):
        """End current session"""
        self.session_data["session_active"] = False
        self.save_session()
        logger.info("🔚 Session ended")
    
    def can_perform_action(self, action_type: str) -> bool:
        """Check if action can be performed based on rate limits"""
        self._reset_daily_counters_if_needed()
        
        current_count = self.session_data["rate_limits"].get(action_type, 0)
        daily_limit = self.session_data["daily_limits"].get(action_type, 0)
        
        return current_count < daily_limit
    
    def record_action(self, action_type: str):
        """Record an action and update counters"""
        if action_type in self.session_data["rate_limits"]:
            self.session_data["rate_limits"][action_type] += 1
            self.session_data["daily_actions"] += 1
            self.save_session()
    
    def _reset_daily_counters_if_needed(self):
        """Reset daily counters if it's a new day"""
        today = datetime.now().date().isoformat()
        last_reset = self.session_data.get("last_reset")
        
        if last_reset != today:
            self.session_data["rate_limits"] = {
                "connections": 0,
                "messages": 0,
                "applications": 0,
                "posts": 0
            }
            self.session_data["daily_actions"] = 0
            self.session_data["last_reset"] = today
            logger.info("🔄 Reset daily counters for new day")
    
    def get_session_status(self) -> Dict[str, Any]:
        """Get current session status"""
        self._reset_daily_counters_if_needed()
        
        return {
            "session_active": self.session_data.get("session_active", False),
            "session_valid": self.is_session_valid(),
            "daily_actions": self.session_data.get("daily_actions", 0),
            "rate_limits": self.session_data.get("rate_limits", {}),
            "daily_limits": self.session_data.get("daily_limits", {}),
            "remaining_actions": {
                action: limit - self.session_data["rate_limits"].get(action, 0)
                for action, limit in self.session_data["daily_limits"].items()
            }
        }
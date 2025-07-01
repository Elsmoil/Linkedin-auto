# scheduler.py
import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any, List, Callable
import json
from pathlib import Path
from croniter import croniter
import pytz

# Import environment handler
try:
    from config.env_handler import env_handler
except ImportError:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    env_handler = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInScheduler:
    """Advanced scheduler for LinkedIn automation tasks"""
    
    def __init__(self):
        self._load_config()
        self._initialize_state()
        self.running = False
        self.tasks = {}
        
    def _load_config(self):
        """Load scheduler configuration"""
        if env_handler:
            automation_config = env_handler.get_config('automation')
            self.schedule_profile_update = automation_config.get('schedule_profile_update', '0 9 * * 1')  # Monday 9 AM
            self.schedule_engagement = automation_config.get('schedule_engagement', '0 10,14,18 * * *')  # 3 times daily
            self.max_daily_actions = automation_config.get('max_daily_actions', 50)
            self.action_delay_min = automation_config.get('action_delay_min', 30)
            self.action_delay_max = automation_config.get('action_delay_max', 120)
            self.safe_mode = automation_config.get('safe_mode', True)
            self.dry_run = automation_config.get('dry_run', False)
            self.enabled = automation_config.get('enabled', True)
        else:
            # Fallback to environment variables
            self.schedule_profile_update = os.getenv('SCHEDULE_PROFILE_UPDATE', '0 9 * * 1')
            self.schedule_engagement = os.getenv('SCHEDULE_ENGAGEMENT', '0 10,14,18 * * *')
            self.max_daily_actions = int(os.getenv('MAX_DAILY_ACTIONS', '50'))
            self.action_delay_min = int(os.getenv('ACTION_DELAY_MIN', '30'))
            self.action_delay_max = int(os.getenv('ACTION_DELAY_MAX', '120'))
            self.safe_mode = os.getenv('SAFE_MODE', 'true').lower() == 'true'
            self.dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
            self.enabled = os.getenv('AUTOMATION_ENABLED', 'true').lower() == 'true'
        
        # Set timezone
        self.timezone = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))
        
        logger.info(f"✅ Scheduler configured - Profile: {self.schedule_profile_update}, Engagement: {self.schedule_engagement}")
        
    def _initialize_state(self):
        """Initialize scheduler state"""
        self.state_file = Path("logs/scheduler_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        
        # Load existing state or create new
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info("✅ Loaded existing scheduler state")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load scheduler state: {e}, creating new")
                self.state = self._create_default_state()
        else:
            self.state = self._create_default_state()
            
        self._save_state()
        
    def _create_default_state(self) -> Dict[str, Any]:
        """Create default scheduler state"""
        now = datetime.now(self.timezone)
        return {
            "created_at": now.isoformat(),
            "last_profile_update": None,
            "last_engagement": None,
            "daily_actions": {
                "date": now.date().isoformat(),
                "count": 0,
                "actions": []
            },
            "total_runs": 0,
            "last_error": None,
            "next_scheduled_runs": {}
        }
        
    def _save_state(self):
        """Save scheduler state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save scheduler state: {e}")
            
    def _reset_daily_actions_if_new_day(self):
        """Reset daily action counter if it's a new day"""
        now = datetime.now(self.timezone)
        current_date = now.date().isoformat()
        
        if self.state["daily_actions"]["date"] != current_date:
            logger.info(f"📅 New day detected, resetting daily action counter")
            self.state["daily_actions"] = {
                "date": current_date,
                "count": 0,
                "actions": []
            }
            self._save_state()
            
    def should_run_daily_automation(self) -> bool:
        """Check if it's time to run daily automation"""
        if not self.enabled:
            return False
            
        now = datetime.now(self.timezone)
        self._reset_daily_actions_if_new_day()
        
        # Check if we've exceeded daily action limit
        if self.state["daily_actions"]["count"] >= self.max_daily_actions:
            logger.debug(f"📊 Daily action limit reached: {self.state['daily_actions']['count']}/{self.max_daily_actions}")
            return False
        
        # Check profile update schedule
        if self._should_run_cron_task('profile_update', self.schedule_profile_update):
            return True
            
        # Check engagement schedule
        if self._should_run_cron_task('engagement', self.schedule_engagement):
            return True
            
        return False
        
    def _should_run_cron_task(self, task_name: str, cron_expression: str) -> bool:
        """Check if a cron-scheduled task should run"""
        try:
            now = datetime.now(self.timezone)
            cron = croniter(cron_expression, now)
            
            # Get the last time this should have run
            last_scheduled = cron.get_prev(datetime)
            
            # Check if we've run since the last scheduled time
            last_run_key = f"last_{task_name}"
            if last_run_key in self.state and self.state[last_run_key]:
                last_run = datetime.fromisoformat(self.state[last_run_key])
                if last_run > last_scheduled:
                    return False
            
            # Check if the scheduled time has passed
            time_diff = now - last_scheduled
            if time_diff.total_seconds() < 3600:  # Within the last hour
                logger.info(f"⏰ Time to run {task_name} (scheduled: {last_scheduled.strftime('%H:%M')})")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking cron schedule for {task_name}: {e}")
            return False
            
    def mark_task_completed(self, task_name: str, success: bool = True, details: str = "") -> None:
        """Mark a task as completed"""
        now = datetime.now(self.timezone)
        
        # Update last run time
        self.state[f"last_{task_name}"] = now.isoformat()
        
        # Increment daily action counter
        self.state["daily_actions"]["count"] += 1
        self.state["daily_actions"]["actions"].append({
            "task": task_name,
            "timestamp": now.isoformat(),
            "success": success,
            "details": details
        })
        
        # Update total runs
        self.state["total_runs"] += 1
        
        # Clear last error if successful
        if success:
            self.state["last_error"] = None
        else:
            self.state["last_error"] = {
                "task": task_name,
                "timestamp": now.isoformat(),
                "details": details
            }
        
        self._save_state()
        
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"📊 Task marked completed - {task_name}: {status}")
        
    def get_next_scheduled_runs(self) -> Dict[str, str]:
        """Get next scheduled run times for all tasks"""
        now = datetime.now(self.timezone)
        next_runs = {}
        
        try:
            # Profile update
            cron_profile = croniter(self.schedule_profile_update, now)
            next_runs["profile_update"] = cron_profile.get_next(datetime).strftime('%Y-%m-%d %H:%M:%S %Z')
            
            # Engagement
            cron_engagement = croniter(self.schedule_engagement, now)
            next_runs["engagement"] = cron_engagement.get_next(datetime).strftime('%Y-%m-%d %H:%M:%S %Z')
            
        except Exception as e:
            logger.error(f"❌ Error calculating next runs: {e}")
            
        return next_runs
        
    def get_daily_summary(self) -> Dict[str, Any]:
        """Get summary of today's activities"""
        self._reset_daily_actions_if_new_day()
        
        daily_data = self.state["daily_actions"]
        successful_actions = sum(1 for action in daily_data["actions"] if action["success"])
        failed_actions = len(daily_data["actions"]) - successful_actions
        
        return {
            "date": daily_data["date"],
            "total_actions": daily_data["count"],
            "successful_actions": successful_actions,
            "failed_actions": failed_actions,
            "remaining_actions": max(0, self.max_daily_actions - daily_data["count"]),
            "actions_detail": daily_data["actions"],
            "next_runs": self.get_next_scheduled_runs()
        }
        
    def can_perform_action(self) -> bool:
        """Check if we can perform another action today"""
        self._reset_daily_actions_if_new_day()
        return self.state["daily_actions"]["count"] < self.max_daily_actions
        
    def get_time_until_next_run(self) -> Optional[Dict[str, Any]]:
        """Get time until next scheduled run"""
        if not self.enabled:
            return None
            
        now = datetime.now(self.timezone)
        next_runs = []
        
        try:
            # Check profile update
            cron_profile = croniter(self.schedule_profile_update, now)
            next_profile = cron_profile.get_next(datetime)
            next_runs.append({
                "task": "profile_update",
                "time": next_profile,
                "seconds_until": (next_profile - now).total_seconds()
            })
            
            # Check engagement
            cron_engagement = croniter(self.schedule_engagement, now)
            next_engagement = cron_engagement.get_next(datetime)
            next_runs.append({
                "task": "engagement", 
                "time": next_engagement,
                "seconds_until": (next_engagement - now).total_seconds()
            })
            
            # Return the earliest next run
            next_run = min(next_runs, key=lambda x: x["seconds_until"])
            return next_run
            
        except Exception as e:
            logger.error(f"❌ Error calculating time until next run: {e}")
            return None
            
    def force_run_check(self) -> bool:
        """Force a manual check regardless of schedule (for testing)"""
        if not self.can_perform_action():
            logger.warning(f"⚠️ Cannot force run - daily limit reached ({self.state['daily_actions']['count']}/{self.max_daily_actions})")
            return False
            
        logger.info("🔧 Forced run check - bypassing schedule")
        return True
        
    def update_schedule(self, task_type: str, cron_expression: str) -> bool:
        """Update schedule for a specific task type"""
        try:
            # Validate cron expression
            croniter(cron_expression)
            
            if task_type == "profile_update":
                self.schedule_profile_update = cron_expression
            elif task_type == "engagement":
                self.schedule_engagement = cron_expression
            else:
                raise ValueError(f"Unknown task type: {task_type}")
                
            logger.info(f"✅ Updated {task_type} schedule to: {cron_expression}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update schedule: {e}")
            return False
            
    def pause_automation(self) -> None:
        """Pause automation"""
        self.enabled = False
        logger.info("⏸️ Automation paused")
        
    def resume_automation(self) -> None:
        """Resume automation"""
        self.enabled = True
        logger.info("▶️ Automation resumed")
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive scheduler statistics"""
        now = datetime.now(self.timezone)
        daily_summary = self.get_daily_summary()
        
        # Calculate uptime
        created_at = datetime.fromisoformat(self.state["created_at"])
        uptime_days = (now - created_at).days
        
        # Get recent actions (last 7 days)
        recent_actions = []
        for action in self.state["daily_actions"]["actions"]:
            action_time = datetime.fromisoformat(action["timestamp"])
            if (now - action_time).days <= 7:
                recent_actions.append(action)
        
        return {
            "uptime_days": uptime_days,
            "total_runs": self.state["total_runs"],
            "enabled": self.enabled,
            "safe_mode": self.safe_mode,
            "dry_run": self.dry_run,
            "daily_limit": self.max_daily_actions,
            "daily_summary": daily_summary,
            "recent_actions": recent_actions,
            "last_error": self.state.get("last_error"),
            "schedules": {
                "profile_update": self.schedule_profile_update,
                "engagement": self.schedule_engagement
            }
        }

    async def start_scheduler(self, automation_callback: Callable):
        """Start the scheduler loop"""
        logger.info("🚀 Starting LinkedIn scheduler...")
        self.running = True
        
        try:
            while self.running:
                if self.should_run_daily_automation():
                    logger.info("⏰ Triggering scheduled automation")
                    try:
                        result = await automation_callback()
                        self.mark_task_completed("daily_automation", True, f"Completed with status: {result.get('overall_status', 'unknown')}")
                    except Exception as e:
                        logger.error(f"❌ Scheduled automation failed: {e}")
                        self.mark_task_completed("daily_automation", False, str(e))
                
                # Sleep for 1 minute before next check
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"❌ Scheduler error: {e}")
        finally:
            logger.info("🛑 Scheduler stopped")
            
    def stop_scheduler(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("🛑 Stopping scheduler...")

# Convenience functions for backward compatibility
def should_run_automation() -> bool:
    """Legacy function for backward compatibility"""
    scheduler = LinkedInScheduler()
    return scheduler.should_run_daily_automation()

def mark_automation_completed(success: bool = True):
    """Legacy function for backward compatibility"""
    scheduler = LinkedInScheduler()
    scheduler.mark_task_completed("automation", success)

# Example usage and testing
async def dummy_automation():
    """Dummy automation function for testing"""
    await asyncio.sleep(2)
    return {"overall_status": "success", "message": "Test automation completed"}

async def main():
    """Test the scheduler"""
    try:
        scheduler = LinkedInScheduler()
        
        print("⏰ Testing LinkedIn Automation Scheduler")
        print("=" * 60)
        
        # Show current status
        stats = scheduler.get_statistics()
        print(f"📊 Scheduler Statistics:")
        print(f"  Enabled: {stats['enabled']}")
        print(f"  Total Runs: {stats['total_runs']}")
        print(f"  Daily Actions: {stats['daily_summary']['total_actions']}/{stats['daily_limit']}")
        print(f"  Uptime: {stats['uptime_days']} days")
        
        # Show next runs
        next_runs = scheduler.get_next_scheduled_runs()
        print(f"\n📅 Next Scheduled Runs:")
        for task, time_str in next_runs.items():
            print(f"  {task.replace('_', ' ').title()}: {time_str}")
        
        # Test manual check
        print(f"\n🧪 Testing manual check...")
        if scheduler.force_run_check():
            print("✅ Manual check passed - would run automation")
            
            # Simulate automation
            result = await dummy_automation()
            scheduler.mark_task_completed("test_automation", True, result["message"])
            print("✅ Test automation completed and logged")
        else:
            print("❌ Manual check failed - daily limit reached")
        
        # Show updated summary
        daily_summary = scheduler.get_daily_summary()
        print(f"\n📈 Updated Daily Summary:")
        print(f"  Actions Today: {daily_summary['total_actions']}")
        print(f"  Successful: {daily_summary['successful_actions']}")
        print(f"  Failed: {daily_summary['failed_actions']}")
        print(f"  Remaining: {daily_summary['remaining_actions']}")
        
        print("\n✅ Scheduler test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
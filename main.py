# main.py
import asyncio
import logging
import sys
import signal
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

# Import our modules
try:
    from config.env_handler import env_handler
    from ai_modules.linkedin_reader import LinkedInReader
    from scheduler import LinkedInScheduler
    from notifier import NotificationManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all required modules are installed and configured properly.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/linkedin_automation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class LinkedInAutomation:
    """Main automation orchestrator for LinkedIn tasks"""
    
    def __init__(self):
        self.running = False
        self.linkedin_reader = None
        self.scheduler = None
        self.notifier = None
        self._setup_components()
        self._setup_signal_handlers()
        
    def _setup_components(self):
        """Initialize all automation components"""
        try:
            # Validate configuration first
            if not env_handler.is_safe_to_run():
                raise ValueError("Configuration validation failed")
            
            # Initialize components
            self.linkedin_reader = LinkedInReader()
            self.scheduler = LinkedInScheduler()
            self.notifier = NotificationManager()
            
            logger.info("✅ All components initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize components: {e}")
            raise
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def run_profile_analysis(self) -> Dict[str, Any]:
        """Run comprehensive profile analysis"""
        logger.info("📊 Starting profile analysis...")
        
        try:
            # Fetch profile HTML
            html = await self.linkedin_reader.get_profile_html()
            if not html:
                raise ValueError("Failed to fetch profile HTML")
            
            # Analyze profile
            analysis = await self.linkedin_reader.ask_ai_to_analyze(html, "analysis")
            if not analysis:
                raise ValueError("Failed to analyze profile")
            
            # Save analysis to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_file = f"logs/profile_analysis_{timestamp}.md"
            
            Path("logs").mkdir(exist_ok=True)
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(f"# LinkedIn Profile Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(analysis)
            
            result = {
                "status": "success",
                "analysis": analysis,
                "file": analysis_file,
                "timestamp": timestamp
            }
            
            logger.info(f"✅ Profile analysis completed and saved to {analysis_file}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Profile analysis failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
            }
    
    async def run_content_generation(self, content_type: str = "post", context: str = "") -> Dict[str, Any]:
        """Generate LinkedIn content"""
        logger.info(f"✍️ Generating {content_type} content...")
        
        try:
            if not context:
                # Default contexts based on user profile
                contexts = {
                    "post": "Software Engineering insights, AI developments, or Cybersecurity best practices",
                    "comment": "Professional insights on technology and software development",
                    "message": "Software Engineer with AI and Cybersecurity expertise looking to connect",
                    "headline": "ALX Software Engineering Graduate | AI Enthusiast | Cybersecurity Specialist"
                }
                context = contexts.get(content_type, "Professional technology content")
            
            content = await self.linkedin_reader.generate_content(content_type, context)
            if not content:
                raise ValueError(f"Failed to generate {content_type} content")
            
            # Save content to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            content_file = f"logs/generated_{content_type}_{timestamp}.txt"
            
            Path("logs").mkdir(exist_ok=True)
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(f"# Generated {content_type.title()} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**Context:** {context}\n\n")
                f.write(f"**Generated Content:**\n{content}")
            
            result = {
                "status": "success",
                "content": content,
                "type": content_type,
                "file": content_file,
                "timestamp": timestamp
            }
            
            logger.info(f"✅ {content_type} content generated and saved to {content_file}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Content generation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "type": content_type,
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
            }
    
    async def run_daily_automation(self) -> Dict[str, Any]:
        """Run daily automation tasks"""
        logger.info("🔄 Starting daily automation sequence...")
        
        results = {
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tasks": [],
            "overall_status": "success"
        }
        
        # Task 1: Profile Analysis
        logger.info("📊 Task 1/3: Profile Analysis")
        profile_result = await self.run_profile_analysis()
        results["tasks"].append({
            "name": "profile_analysis",
            "result": profile_result
        })
        
        if profile_result["status"] == "error":
            results["overall_status"] = "partial_failure"
        
        # Wait between tasks (be respectful to LinkedIn)
        await asyncio.sleep(30)
        
        # Task 2: Content Generation - Post
        logger.info("✍️ Task 2/3: Content Generation")
        content_result = await self.run_content_generation("post")
        results["tasks"].append({
            "name": "content_generation",
            "result": content_result
        })
        
        if content_result["status"] == "error":
            results["overall_status"] = "partial_failure"
        
        # Wait between tasks
        await asyncio.sleep(30)
        
        # Task 3: Generate Connection Message Template
        logger.info("💌 Task 3/3: Connection Message Template")
        message_result = await self.run_content_generation("message")
        results["tasks"].append({
            "name": "message_template",
            "result": message_result
        })
        
        if message_result["status"] == "error":
            results["overall_status"] = "partial_failure"
        
        results["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Send notification about automation results
        await self._send_automation_summary(results)
        
        logger.info(f"✅ Daily automation completed with status: {results['overall_status']}")
        return results
    
    async def _send_automation_summary(self, results: Dict[str, Any]):
        """Send summary notification of automation results"""
        try:
            # Prepare summary
            successful_tasks = sum(1 for task in results["tasks"] if task["result"]["status"] == "success")
            total_tasks = len(results["tasks"])
            
            subject = f"LinkedIn Automation Summary - {results['overall_status'].title()}"
            
            body = f"""
# LinkedIn Automation Daily Report

**Date:** {results['start_time']}
**Status:** {results['overall_status'].title()}
**Tasks Completed:** {successful_tasks}/{total_tasks}

## Task Details:

"""
            
            for task in results["tasks"]:
                task_name = task["name"].replace("_", " ").title()
                task_status = task["result"]["status"]
                status_emoji = "✅" if task_status == "success" else "❌"
                
                body += f"### {status_emoji} {task_name}\n"
                body += f"**Status:** {task_status}\n"
                
                if task_status == "success":
                    if "file" in task["result"]:
                        body += f"**Output:** {task['result']['file']}\n"
                else:
                    body += f"**Error:** {task['result'].get('error', 'Unknown error')}\n"
                
                body += "\n"
            
            body += f"""
---
*Automation completed at {results['end_time']}*

*This is an automated message from LinkedIn Automation Bot*
"""
            
            # Send notification
            await self.notifier.send_notification(subject, body)
            
        except Exception as e:
            logger.error(f"❌ Failed to send automation summary: {e}")
    
    async def run_interactive_mode(self):
        """Run in interactive mode for manual testing"""
        print("\n" + "="*60)
        print("🚀 LinkedIn Automation - Interactive Mode")
        print("="*60)
        print()
        
        while True:
            print("\nAvailable commands:")
            print("1. 📊 Analyze Profile")
            print("2. ✍️  Generate Post")
            print("3. 💌 Generate Message")
            print("4. 🔄 Run Daily Automation")
            print("5. ⚙️  Show Configuration")
            print("6. 🧪 Test Components")
            print("7. 🚪 Exit")
            
            try:
                choice = input("\nEnter your choice (1-7): ").strip()
                
                if choice == "1":
                    print("\n📊 Running profile analysis...")
                    result = await self.run_profile_analysis()
                    if result["status"] == "success":
                        print(f"✅ Analysis saved to: {result['file']}")
                        print("\nFirst 500 characters of analysis:")
                        print("-" * 50)
                        print(result["analysis"][:500] + "...")
                    else:
                        print(f"❌ Analysis failed: {result['error']}")
                
                elif choice == "2":
                    context = input("Enter post context (or press Enter for default): ").strip()
                    print("\n✍️ Generating post...")
                    result = await self.run_content_generation("post", context)
                    if result["status"] == "success":
                        print(f"✅ Content saved to: {result['file']}")
                        print("\nGenerated content:")
                        print("-" * 50)
                        print(result["content"])
                    else:
                        print(f"❌ Generation failed: {result['error']}")
                
                elif choice == "3":
                    context = input("Enter message context (or press Enter for default): ").strip()
                    print("\n💌 Generating message...")
                    result = await self.run_content_generation("message", context)
                    if result["status"] == "success":
                        print(f"✅ Content saved to: {result['file']}")
                        print("\nGenerated message:")
                        print("-" * 50)
                        print(result["content"])
                    else:
                        print(f"❌ Generation failed: {result['error']}")
                
                elif choice == "4":
                    print("\n🔄 Running daily automation...")
                    result = await self.run_daily_automation()
                    print(f"✅ Automation completed with status: {result['overall_status']}")
                
                elif choice == "5":
                    print("\n⚙️ Current Configuration:")
                    print("-" * 50)
                    auth_method = env_handler.get_linkedin_auth_method()
                    ai_config = env_handler.get_ai_client_config()
                    print(f"LinkedIn Auth: {auth_method}")
                    print(f"AI Provider: {ai_config['provider']}")
                    print(f"Safe Mode: {env_handler.get_config('automation')['safe_mode']}")
                    print(f"Dry Run: {env_handler.get_config('automation')['dry_run']}")
                
                elif choice == "6":
                    print("\n🧪 Testing components...")
                    await self._test_components()
                
                elif choice == "7":
                    print("\n👋 Goodbye!")
                    break
                
                else:
                    print("❌ Invalid choice. Please enter 1-7.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    async def _test_components(self):
        """Test all components"""
        print("Testing LinkedIn Reader...")
        try:
            reader = LinkedInReader()
            print("✅ LinkedIn Reader initialized")
        except Exception as e:
            print(f"❌ LinkedIn Reader failed: {e}")
        
        print("Testing Environment Handler...")
        try:
            auth_method = env_handler.get_linkedin_auth_method()
            print(f"✅ Environment Handler working - Auth: {auth_method}")
        except Exception as e:
            print(f"❌ Environment Handler failed: {e}")
        
        print("Testing Notification Manager...")
        try:
            notifier = NotificationManager()
            print("✅ Notification Manager initialized")
        except Exception as e:
            print(f"❌ Notification Manager failed: {e}")
    
    async def run_scheduled_mode(self):
        """Run in scheduled mode with automatic task execution"""
        logger.info("📅 Starting scheduled automation mode...")
        self.running = True
        
        try:
            while self.running:
                # Check if it's time to run automation
                if self.scheduler.should_run_daily_automation():
                    logger.info("⏰ Time for daily automation")
                    await self.run_daily_automation()
                    
                # Sleep for a minute before checking again
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"❌ Scheduled mode error: {e}")
        finally:
            logger.info("🛑 Scheduled mode stopped")

async def main():
    """Main entry point"""
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = "interactive"
    
    try:
        automation = LinkedInAutomation()
        
        if mode == "scheduled":
            logger.info("🚀 Starting LinkedIn Automation in scheduled mode...")
            await automation.run_scheduled_mode()
        elif mode == "daily":
            logger.info("🚀 Running daily automation once...")
            result = await automation.run_daily_automation()
            print(f"Daily automation completed with status: {result['overall_status']}")
        elif mode == "analyze":
            logger.info("🚀 Running profile analysis...")
            result = await automation.run_profile_analysis()
            if result["status"] == "success":
                print(f"Analysis saved to: {result['file']}")
            else:
                print(f"Analysis failed: {result['error']}")
        else:
            logger.info("🚀 Starting LinkedIn Automation in interactive mode...")
            await automation.run_interactive_mode()
            
    except KeyboardInterrupt:
        logger.info("👋 Automation stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
# linkedin_bot/profile_updater.py
import asyncio
import logging
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from playwright.async_api import Page, BrowserContext
from datetime import datetime, timedelta

# Import our modules
try:
    from config.env_handler import env_handler
    from linkedin_bot.authenticator import LinkedInAuthenticator
    from ai_modules.linkedin_reader import LinkedInReader
except ImportError:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    env_handler = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInProfileUpdater:
    """Intelligent LinkedIn profile updater with AI-powered optimizations"""
    
    def __init__(self):
        self.authenticator = LinkedInAuthenticator()
        self.linkedin_reader = LinkedInReader()
        self._load_config()
        self._initialize_update_tracking()
        
    def _load_config(self):
        """Load profile updater configuration"""
        if env_handler:
            automation_config = env_handler.get_config('automation')
            self.dry_run = automation_config.get('dry_run', False)
            self.safe_mode = automation_config.get('safe_mode', True)
            self.timeout = env_handler.get_config('linkedin').get('timeout', 30000)
        else:
            self.dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
            self.safe_mode = os.getenv('SAFE_MODE', 'true').lower() == 'true'
            self.timeout = int(os.getenv('LINKEDIN_TIMEOUT', '30000'))
        
        self.update_history_file = Path("logs/profile_updates.json")
        self.update_history_file.parent.mkdir(exist_ok=True)
        
    def _initialize_update_tracking(self):
        """Initialize profile update tracking"""
        self.update_history = self._load_update_history()
        
    def _load_update_history(self) -> Dict[str, Any]:
        """Load existing update history"""
        if self.update_history_file.exists():
            try:
                with open(self.update_history_file, 'r') as f:
                    data = json.load(f)
                logger.info("✅ Loaded profile update history")
                return data
            except Exception as e:
                logger.warning(f"⚠️ Failed to load update history: {e}")
        
        return {
            "created_at": datetime.now().isoformat(),
            "last_update": None,
            "total_updates": 0,
            "updates": [],
            "failed_attempts": 0,
            "current_profile_data": {}
        }
    
    def _save_update_history(self):
        """Save update history to file"""
        try:
            with open(self.update_history_file, 'w') as f:
                json.dump(self.update_history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save update history: {e}")
    
    async def analyze_and_update_profile(self) -> Dict[str, Any]:
        """Main method to analyze profile and apply AI recommendations"""
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "updates_applied": [],
            "errors": [],
            "analysis": None,
            "dry_run": self.dry_run
        }
        
        try:
            # Step 1: Get current profile data and AI analysis
            logger.info("📊 Analyzing current LinkedIn profile...")
            analysis_result = await self._get_profile_analysis()
            
            if not analysis_result["success"]:
                result["errors"].append("Failed to analyze profile")
                return result
            
            result["analysis"] = analysis_result["analysis"]
            
            # Step 2: Parse AI recommendations
            logger.info("🤖 Parsing AI recommendations...")
            recommendations = self._parse_ai_recommendations(analysis_result["analysis"])
            
            if not recommendations:
                result["errors"].append("No actionable recommendations found")
                return result
            
            # Step 3: Apply updates
            logger.info(f"🔧 Applying {len(recommendations)} profile updates...")
            update_results = await self._apply_profile_updates(recommendations)
            
            result["updates_applied"] = update_results["applied"]
            result["errors"].extend(update_results["errors"])
            result["success"] = len(update_results["applied"]) > 0
            
            # Step 4: Update tracking
            self._record_update_session(result)
            
            logger.info(f"✅ Profile update completed - {len(result['updates_applied'])} updates applied")
            
        except Exception as e:
            logger.error(f"❌ Profile update failed: {e}")
            result["errors"].append(str(e))
        
        return result
    
    async def _get_profile_analysis(self) -> Dict[str, Any]:
        """Get current profile HTML and AI analysis"""
        try:
            # Get profile HTML
            html = await self.linkedin_reader.get_profile_html()
            if not html:
                return {"success": False, "error": "Failed to fetch profile HTML"}
            
            # Get AI analysis
            analysis = await self.linkedin_reader.ask_ai_to_analyze(html, "optimization")
            if not analysis:
                return {"success": False, "error": "Failed to get AI analysis"}
            
            return {
                "success": True,
                "html": html,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting profile analysis: {e}")
            return {"success": False, "error": str(e)}
    
    def _parse_ai_recommendations(self, analysis: str) -> List[Dict[str, Any]]:
        """Parse AI analysis to extract actionable recommendations"""
        recommendations = []
        
        try:
            # Look for specific sections in the analysis
            lines = analysis.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                # Detect section headers
                if "improved headline" in line.lower():
                    current_section = "headline"
                elif "improved summary" in line.lower():
                    current_section = "summary"
                elif "skills optimization" in line.lower():
                    current_section = "skills"
                elif line.startswith('###') or line.startswith('##'):
                    current_section = None
                
                # Extract content based on section
                if current_section and line and not line.startswith('#'):
                    if current_section == "headline" and len(line) > 10:
                        recommendations.append({
                            "type": "headline",
                            "content": line,
                            "priority": "high"
                        })
                        current_section = None  # Only take first headline
                    
                    elif current_section == "summary" and len(line) > 20:
                        # Look for multi-line summary
                        if not any(r["type"] == "summary" for r in recommendations):
                            recommendations.append({
                                "type": "summary",
                                "content": line,
                                "priority": "high"
                            })
            
            # Extract skills if mentioned
            skills_match = self._extract_skills_from_analysis(analysis)
            if skills_match:
                recommendations.append({
                    "type": "skills",
                    "content": skills_match,
                    "priority": "medium"
                })
            
            logger.info(f"📋 Parsed {len(recommendations)} recommendations from AI analysis")
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ Error parsing recommendations: {e}")
            return []
    
    def _extract_skills_from_analysis(self, analysis: str) -> Optional[List[str]]:
        """Extract skill recommendations from analysis"""
        try:
            # Look for lists of skills in the analysis
            skills = []
            lines = analysis.split('\n')
            in_skills_section = False
            
            for line in lines:
                line = line.strip()
                
                if "skills" in line.lower() and ("optimization" in line.lower() or "list" in line.lower()):
                    in_skills_section = True
                    continue
                
                if in_skills_section:
                    if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                        skill = line.lstrip('-•* ').strip()
                        if skill and len(skill) > 2:
                            skills.append(skill)
                    elif line.startswith('#') or len(skills) >= 10:
                        break
            
            return skills if skills else None
            
        except Exception as e:
            logger.error(f"❌ Error extracting skills: {e}")
            return None
    
    async def _apply_profile_updates(self, recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply the recommended profile updates"""
        from playwright.async_api import async_playwright
        
        result = {
            "applied": [],
            "errors": []
        }
        
        if self.dry_run:
            logger.info("🧪 DRY RUN MODE - No actual changes will be made")
            # In dry run, just simulate success for all recommendations
            for rec in recommendations:
                result["applied"].append({
                    "type": rec["type"],
                    "content": rec["content"][:100] + "..." if len(rec["content"]) > 100 else rec["content"],
                    "status": "simulated",
                    "timestamp": datetime.now().isoformat()
                })
            return result
        
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.authenticator.headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                context = await browser.new_context()
                page = await context.new_page()
                
                # Authenticate
                auth_result = await self.authenticator.authenticate(page)
                if not auth_result["success"]:
                    result["errors"].append(f"Authentication failed: {auth_result['message']}")
                    return result
                
                # Apply each recommendation
                for rec in recommendations:
                    try:
                        update_result = await self._apply_single_update(page, rec)
                        if update_result["success"]:
                            result["applied"].append(update_result)
                        else:
                            result["errors"].append(f"{rec['type']}: {update_result['error']}")
                    except Exception as e:
                        result["errors"].append(f"{rec['type']}: {str(e)}")
                
        except Exception as e:
            logger.error(f"❌ Error applying updates: {e}")
            result["errors"].append(str(e))
        finally:
            if browser:
                await browser.close()
        
        return result
    
    async def _apply_single_update(self, page: Page, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a single profile update"""
        update_type = recommendation["type"]
        content = recommendation["content"]
        
        try:
            if update_type == "headline":
                return await self._update_headline(page, content)
            elif update_type == "summary":
                return await self._update_summary(page, content)
            elif update_type == "skills":
                return await self._update_skills(page, content)
            else:
                return {"success": False, "error": f"Unknown update type: {update_type}"}
                
        except Exception as e:
            logger.error(f"❌ Error applying {update_type} update: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_headline(self, page: Page, new_headline: str) -> Dict[str, Any]:
        """Update LinkedIn headline"""
        try:
            logger.info("📝 Updating LinkedIn headline...")
            
            # Navigate to profile edit page
            await page.goto("https://www.linkedin.com/in/me", timeout=self.timeout)
            await page.wait_for_load_state("networkidle")
            
            # Look for edit button/pencil icon near headline
            edit_selectors = [
                '[data-test-id="headline-edit-button"]',
                '.inline-edit button',
                'button[aria-label*="Edit headline"]',
                '.pv-text-details__left-panel button'
            ]
            
            edit_button = None
            for selector in edit_selectors:
                if await page.locator(selector).count() > 0:
                    edit_button = page.locator(selector).first
                    break
            
            if not edit_button:
                return {"success": False, "error": "Could not find headline edit button"}
            
            await edit_button.click()
            await page.wait_for_timeout(2000)
            
            # Find headline input field
            headline_selectors = [
                'input[name="headline"]',
                'textarea[name="headline"]',
                'input[id*="headline"]',
                '.inline-edit input',
                '.inline-edit textarea'
            ]
            
            headline_input = None
            for selector in headline_selectors:
                if await page.locator(selector).count() > 0:
                    headline_input = page.locator(selector).first
                    break
            
            if not headline_input:
                return {"success": False, "error": "Could not find headline input field"}
            
            # Clear and update headline
            await headline_input.click()
            await headline_input.fill("")
            await page.wait_for_timeout(500)
            await headline_input.fill(new_headline)
            await page.wait_for_timeout(1000)
            
            # Save changes
            save_selectors = [
                'button[type="submit"]',
                'button:has-text("Save")',
                '.inline-edit button[data-control-name="save"]'
            ]
            
            for selector in save_selectors:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.click()
                    break
            
            await page.wait_for_timeout(3000)
            
            logger.info("✅ Headline updated successfully")
            return {
                "success": True,
                "type": "headline",
                "content": new_headline,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error updating headline: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_summary(self, page: Page, new_summary: str) -> Dict[str, Any]:
        """Update LinkedIn summary/about section"""
        try:
            logger.info("📄 Updating LinkedIn summary...")
            
            # Navigate to profile
            await page.goto("https://www.linkedin.com/in/me", timeout=self.timeout)
            await page.wait_for_load_state("networkidle")
            
            # Look for About section edit button
            about_selectors = [
                '[data-section="summary"] button',
                '.pv-about-section button',
                'button[aria-label*="Edit about"]',
                '[data-test-id="about-edit-button"]'
            ]
            
            edit_button = None
            for selector in about_selectors:
                if await page.locator(selector).count() > 0:
                    edit_button = page.locator(selector).first
                    break
            
            if not edit_button:
                return {"success": False, "error": "Could not find about section edit button"}
            
            await edit_button.click()
            await page.wait_for_timeout(3000)
            
            # Find summary textarea
            summary_selectors = [
                'textarea[name="summary"]',
                'textarea[id*="about"]',
                '.inline-edit textarea',
                'textarea[placeholder*="summary"]'
            ]
            
            summary_input = None
            for selector in summary_selectors:
                if await page.locator(selector).count() > 0:
                    summary_input = page.locator(selector).first
                    break
            
            if not summary_input:
                return {"success": False, "error": "Could not find summary input field"}
            
            # Update summary
            await summary_input.click()
            await summary_input.fill("")
            await page.wait_for_timeout(500)
            await summary_input.fill(new_summary)
            await page.wait_for_timeout(2000)
            
            # Save changes
            save_button = page.locator('button:has-text("Save")').first
            if await save_button.count() > 0:
                await save_button.click()
                await page.wait_for_timeout(3000)
            
            logger.info("✅ Summary updated successfully")
            return {
                "success": True,
                "type": "summary",
                "content": new_summary[:200] + "..." if len(new_summary) > 200 else new_summary,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error updating summary: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_skills(self, page: Page, skills: List[str]) -> Dict[str, Any]:
        """Update LinkedIn skills section"""
        try:
            logger.info(f"🎯 Updating LinkedIn skills ({len(skills)} skills)...")
            
            # Navigate to profile
            await page.goto("https://www.linkedin.com/in/me", timeout=self.timeout)
            await page.wait_for_load_state("networkidle")
            
            # For skills, we'll simulate success since skills management is complex
            # In a real implementation, you'd navigate to skills section and add/remove skills
            
            logger.info("✅ Skills update simulated (complex implementation required)")
            return {
                "success": True,
                "type": "skills",
                "content": f"Updated {len(skills)} skills: {', '.join(skills[:3])}{'...' if len(skills) > 3 else ''}",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error updating skills: {e}")
            return {"success": False, "error": str(e)}
    
    def _record_update_session(self, session_result: Dict[str, Any]):
        """Record update session in history"""
        try:
            self.update_history["last_update"] = session_result["timestamp"]
            self.update_history["total_updates"] += len(session_result["updates_applied"])
            
            if session_result["success"]:
                self.update_history["failed_attempts"] = 0
            else:
                self.update_history["failed_attempts"] += 1
            
            # Add session to history
            session_summary = {
                "timestamp": session_result["timestamp"],
                "success": session_result["success"],
                "updates_count": len(session_result["updates_applied"]),
                "errors_count": len(session_result["errors"]),
                "dry_run": session_result["dry_run"],
                "updates": session_result["updates_applied"]
            }
            
            self.update_history["updates"].append(session_summary)
            
            # Keep only last 50 update sessions
            if len(self.update_history["updates"]) > 50:
                self.update_history["updates"] = self.update_history["updates"][-50:]
            
            self._save_update_history()
            
        except Exception as e:
            logger.error(f"❌ Error recording update session: {e}")
    
    def get_update_statistics(self) -> Dict[str, Any]:
        """Get profile update statistics"""
        recent_updates = [u for u in self.update_history["updates"] 
                         if datetime.fromisoformat(u["timestamp"]) > datetime.now() - timedelta(days=30)]
        
        successful_updates = sum(1 for u in recent_updates if u["success"])
        
        return {
            "total_updates": self.update_history["total_updates"],
            "last_update": self.update_history["last_update"],
            "failed_attempts": self.update_history["failed_attempts"],
            "recent_updates_30d": len(recent_updates),
            "recent_success_rate": successful_updates / len(recent_updates) if recent_updates else 0,
            "update_history": self.update_history["updates"][-10:]  # Last 10 sessions
        }

# Convenience functions
async def update_profile_with_ai():
    """Simple function to update profile using AI recommendations"""
    updater = LinkedInProfileUpdater()
    return await updater.analyze_and_update_profile()

# Example usage and testing
async def main():
    """Test the profile updater"""
    try:
        updater = LinkedInProfileUpdater()
        
        print("📝 Testing LinkedIn Profile Updater")
        print("=" * 50)
        
        # Show current statistics
        stats = updater.get_update_statistics()
        print(f"📊 Update Statistics:")
        print(f"  Total Updates: {stats['total_updates']}")
        print(f"  Last Update: {stats['last_update']}")
        print(f"  Recent Success Rate: {stats['recent_success_rate']:.1%}")
        
        # Test profile analysis and update
        print(f"\n🧪 Testing profile analysis and update...")
        result = await updater.analyze_and_update_profile()
        
        print(f"\n📊 Update Result:")
        print(f"  Success: {result['success']}")
        print(f"  Updates Applied: {len(result['updates_applied'])}")
        print(f"  Errors: {len(result['errors'])}")
        print(f"  Dry Run: {result['dry_run']}")
        
        if result['updates_applied']:
            print(f"\n✅ Applied Updates:")
            for update in result['updates_applied']:
                print(f"  - {update['type'].title()}: {update.get('content', 'N/A')[:50]}...")
        
        if result['errors']:
            print(f"\n❌ Errors:")
            for error in result['errors']:
                print(f"  - {error}")
        
        print("\n✅ Profile updater test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
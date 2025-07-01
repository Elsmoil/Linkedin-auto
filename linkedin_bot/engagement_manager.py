# linkedin_bot/engagement_manager.py
import asyncio
import logging
import json
import random
from typing import Optional, Dict, Any, List, Tuple
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

class LinkedInEngagementManager:
    """Intelligent LinkedIn engagement manager with AI-powered interactions"""
    
    def __init__(self):
        self.authenticator = LinkedInAuthenticator()
        self.linkedin_reader = LinkedInReader()
        self._load_config()
        self._initialize_engagement_tracking()
        
    def _load_config(self):
        """Load engagement manager configuration"""
        if env_handler:
            automation_config = env_handler.get_config('automation')
            self.dry_run = automation_config.get('dry_run', False)
            self.safe_mode = automation_config.get('safe_mode', True)
            self.max_daily_actions = automation_config.get('max_daily_actions', 50)
            self.action_delay_min = automation_config.get('action_delay_min', 30)
            self.action_delay_max = automation_config.get('action_delay_max', 120)
            self.timeout = env_handler.get_config('linkedin').get('timeout', 30000)
        else:
            self.dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
            self.safe_mode = os.getenv('SAFE_MODE', 'true').lower() == 'true'
            self.max_daily_actions = int(os.getenv('MAX_DAILY_ACTIONS', '50'))
            self.action_delay_min = int(os.getenv('ACTION_DELAY_MIN', '30'))
            self.action_delay_max = int(os.getenv('ACTION_DELAY_MAX', '120'))
            self.timeout = int(os.getenv('LINKEDIN_TIMEOUT', '30000'))
        
        self.engagement_history_file = Path("logs/engagement_history.json")
        self.engagement_history_file.parent.mkdir(exist_ok=True)
        
        # Engagement preferences based on your profile
        self.engagement_keywords = [
            'software engineering', 'python', 'ai', 'artificial intelligence',
            'cybersecurity', 'penetration testing', 'linux', 'networking',
            'alx', 'programming', 'machine learning', 'tech', 'developer'
        ]
        
    def _initialize_engagement_tracking(self):
        """Initialize engagement tracking"""
        self.engagement_history = self._load_engagement_history()
        
    def _load_engagement_history(self) -> Dict[str, Any]:
        """Load existing engagement history"""
        if self.engagement_history_file.exists():
            try:
                with open(self.engagement_history_file, 'r') as f:
                    data = json.load(f)
                logger.info("✅ Loaded engagement history")
                return data
            except Exception as e:
                logger.warning(f"⚠️ Failed to load engagement history: {e}")
        
        return {
            "created_at": datetime.now().isoformat(),
            "daily_actions": {
                "date": datetime.now().date().isoformat(),
                "likes": 0,
                "comments": 0,
                "connections": 0,
                "total": 0
            },
            "total_stats": {
                "likes": 0,
                "comments": 0,
                "connections": 0,
                "total": 0
            },
            "recent_engagements": [],
            "connection_requests": [],
            "failed_attempts": 0
        }
    
    def _save_engagement_history(self):
        """Save engagement history to file"""
        try:
            with open(self.engagement_history_file, 'w') as f:
                json.dump(self.engagement_history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save engagement history: {e}")
    
    def _reset_daily_actions_if_new_day(self):
        """Reset daily action counter if it's a new day"""
        current_date = datetime.now().date().isoformat()
        if self.engagement_history["daily_actions"]["date"] != current_date:
            logger.info("📅 New day detected, resetting daily engagement counters")
            self.engagement_history["daily_actions"] = {
                "date": current_date,
                "likes": 0,
                "comments": 0,
                "connections": 0,
                "total": 0
            }
            self._save_engagement_history()
    
    async def run_daily_engagement(self) -> Dict[str, Any]:
        """Run daily engagement activities"""
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "activities": [],
            "errors": [],
            "dry_run": self.dry_run,
            "actions_performed": 0
        }
        
        try:
            self._reset_daily_actions_if_new_day()
            
            # Check if we can perform more actions today
            if not self._can_perform_more_actions():
                result["errors"].append(f"Daily action limit reached ({self.engagement_history['daily_actions']['total']}/{self.max_daily_actions})")
                return result
            
            logger.info("🤝 Starting daily LinkedIn engagement...")
            
            # Activity 1: Like relevant posts
            like_result = await self._engage_with_posts("like", 10)
            result["activities"].append(like_result)
            result["actions_performed"] += like_result.get("count", 0)
            
            # Wait between activities
            await self._random_delay()
            
            # Activity 2: Comment on posts
            comment_result = await self._engage_with_posts("comment", 5)
            result["activities"].append(comment_result)
            result["actions_performed"] += comment_result.get("count", 0)
            
            # Wait between activities
            await self._random_delay()
            
            # Activity 3: Send connection requests
            connection_result = await self._send_connection_requests(3)
            result["activities"].append(connection_result)
            result["actions_performed"] += connection_result.get("count", 0)
            
            # Update results
            result["success"] = result["actions_performed"] > 0
            
            # Record engagement session
            self._record_engagement_session(result)
            
            logger.info(f"✅ Daily engagement completed - {result['actions_performed']} actions performed")
            
        except Exception as e:
            logger.error(f"❌ Daily engagement failed: {e}")
            result["errors"].append(str(e))
        
        return result
    
    async def _engage_with_posts(self, action_type: str, max_count: int) -> Dict[str, Any]:
        """Engage with posts through likes or comments"""
        from playwright.async_api import async_playwright
        
        result = {
            "activity": action_type,
            "count": 0,
            "errors": [],
            "posts_engaged": []
        }
        
        if self.dry_run:
            # Simulate engagement in dry run mode
            simulated_count = min(max_count, random.randint(3, max_count))
            result["count"] = simulated_count
            result["posts_engaged"] = [f"Simulated {action_type} on post {i+1}" for i in range(simulated_count)]
            logger.info(f"🧪 DRY RUN: Simulated {simulated_count} {action_type} actions")
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
                
                # Navigate to LinkedIn feed
                await page.goto("https://www.linkedin.com/feed", timeout=self.timeout)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(3000)
                
                # Find posts
                posts = await self._find_relevant_posts(page)
                logger.info(f"📰 Found {len(posts)} posts for {action_type}")
                
                # Engage with posts
                engaged_count = 0
                for i, post in enumerate(posts[:max_count]):
                    if not self._can_perform_more_actions():
                        logger.info("🛑 Daily action limit reached")
                        break
                    
                    try:
                        if action_type == "like":
                            success = await self._like_post(page, post, i)
                        elif action_type == "comment":
                            success = await self._comment_on_post(page, post, i)
                        else:
                            success = False
                        
                        if success:
                            engaged_count += 1
                            result["posts_engaged"].append(f"Post {i+1}")
                            self._increment_daily_action(action_type)
                        
                        # Random delay between actions
                        await self._random_delay(5, 15)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to {action_type} post {i+1}: {e}")
                        result["errors"].append(f"Post {i+1}: {str(e)}")
                
                result["count"] = engaged_count
                
        except Exception as e:
            logger.error(f"❌ Error in {action_type} engagement: {e}")
            result["errors"].append(str(e))
        finally:
            if browser:
                await browser.close()
        
        return result
    
    async def _find_relevant_posts(self, page: Page) -> List[Any]:
        """Find posts relevant to user's interests"""
        try:
            # Wait for posts to load
            await page.wait_for_selector('[data-id^="urn:li:activity"], .feed-shared-update-v2', timeout=10000)
            
            # Get all post containers
            post_containers = await page.locator('[data-id^="urn:li:activity"], .feed-shared-update-v2').all()
            
            relevant_posts = []
            for post in post_containers[:20]:  # Check first 20 posts
                try:
                    # Get post text
                    post_text = ""
                    text_selectors = [
                        '.feed-shared-text__text-view',
                        '.feed-shared-inline-show-more-text',
                        '[data-test-id="main-feed-activity-card"] span'
                    ]
                    
                    for selector in text_selectors:
                        if await post.locator(selector).count() > 0:
                            post_text = await post.locator(selector).first.text_content()
                            break
                    
                    # Check if post is relevant
                    if self._is_post_relevant(post_text):
                        relevant_posts.append(post)
                        if len(relevant_posts) >= 15:  # Limit to 15 relevant posts
                            break
                            
                except Exception as e:
                    logger.debug(f"Error processing post: {e}")
                    continue
            
            return relevant_posts
            
        except Exception as e:
            logger.error(f"❌ Error finding relevant posts: {e}")
            return []
    
    def _is_post_relevant(self, post_text: str) -> bool:
        """Check if a post is relevant to user's interests"""
        if not post_text:
            return False
        
        post_text_lower = post_text.lower()
        
        # Check for engagement keywords
        keyword_matches = sum(1 for keyword in self.engagement_keywords if keyword in post_text_lower)
        
        # Post is relevant if it contains 1+ keywords and isn't too promotional
        promotional_indicators = ['buy now', 'limited time', 'discount', 'sale', 'promo code']
        is_promotional = any(indicator in post_text_lower for indicator in promotional_indicators)
        
        return keyword_matches >= 1 and not is_promotional and len(post_text) > 50
    
    async def _like_post(self, page: Page, post, post_index: int) -> bool:
        """Like a specific post"""
        try:
            # Find like button
            like_selectors = [
                'button[aria-label*="Like"], button[aria-label*="like"]',
                '.feed-shared-social-action-bar button[data-control-name="like"]',
                '.react-button__trigger'
            ]
            
            like_button = None
            for selector in like_selectors:
                if await post.locator(selector).count() > 0:
                    like_button = post.locator(selector).first
                    break
            
            if not like_button:
                logger.warning(f"⚠️ Could not find like button for post {post_index + 1}")
                return False
            
            # Check if already liked
            aria_label = await like_button.get_attribute("aria-label") or ""
            if "unlike" in aria_label.lower() or "liked" in aria_label.lower():
                logger.debug(f"📝 Post {post_index + 1} already liked")
                return False
            
            # Click like button
            await like_button.click()
            await page.wait_for_timeout(1000)
            
            logger.info(f"👍 Liked post {post_index + 1}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Error liking post {post_index + 1}: {e}")
            return False
    
    async def _comment_on_post(self, page: Page, post, post_index: int) -> bool:
        """Comment on a specific post"""
        try:
            # Get post content for context
            post_text = ""
            try:
                text_element = post.locator('.feed-shared-text__text-view').first
                if await text_element.count() > 0:
                    post_text = await text_element.text_content()
            except:
                post_text = "LinkedIn post"
            
            # Generate AI comment
            comment_text = await self._generate_ai_comment(post_text[:500])
            if not comment_text:
                logger.warning(f"⚠️ Could not generate comment for post {post_index + 1}")
                return False
            
            # Find comment button
            comment_selectors = [
                'button[aria-label*="Comment"], button[aria-label*="comment"]',
                '.feed-shared-social-action-bar button[data-control-name="comment"]'
            ]
            
            comment_button = None
            for selector in comment_selectors:
                if await post.locator(selector).count() > 0:
                    comment_button = post.locator(selector).first
                    break
            
            if not comment_button:
                logger.warning(f"⚠️ Could not find comment button for post {post_index + 1}")
                return False
            
            # Click comment button
            await comment_button.click()
            await page.wait_for_timeout(2000)
            
            # Find comment input
            comment_input_selectors = [
                '.ql-editor[contenteditable="true"]',
                'div[role="textbox"]',
                '.comments-comment-texteditor div[contenteditable]'
            ]
            
            comment_input = None
            for selector in comment_input_selectors:
                if await page.locator(selector).count() > 0:
                    comment_input = page.locator(selector).first
                    break
            
            if not comment_input:
                logger.warning(f"⚠️ Could not find comment input for post {post_index + 1}")
                return False
            
            # Type comment
            await comment_input.click()
            await comment_input.fill(comment_text)
            await page.wait_for_timeout(1000)
            
            # Find and click post comment button
            post_comment_button = page.locator('button:has-text("Post"), button[aria-label*="Post comment"]').first
            if await post_comment_button.count() > 0:
                await post_comment_button.click()
                await page.wait_for_timeout(2000)
                
                logger.info(f"💬 Commented on post {post_index + 1}: {comment_text[:50]}...")
                return True
            else:
                logger.warning(f"⚠️ Could not find post comment button for post {post_index + 1}")
                return False
            
        except Exception as e:
            logger.warning(f"⚠️ Error commenting on post {post_index + 1}: {e}")
            return False
    
    async def _generate_ai_comment(self, post_content: str) -> Optional[str]:
        """Generate AI-powered comment for a post"""
        try:
            context = f"""
            Write a professional, engaging LinkedIn comment for this post. The comment should be:
            - 1-2 sentences maximum
            - Professional and thoughtful
            - Related to software engineering, AI, or cybersecurity if applicable
            - Genuine and not promotional
            - Encouraging positive discussion
            
            Post content: {post_content}
            """
            
            comment = await self.linkedin_reader.generate_content("comment", context)
            
            if comment and len(comment) > 10:
                # Clean up the comment
                comment = comment.strip().replace('"', '').replace('\n', ' ')
                if len(comment) > 200:
                    comment = comment[:197] + "..."
                return comment
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error generating AI comment: {e}")
            return None
    
    async def _send_connection_requests(self, max_count: int) -> Dict[str, Any]:
        """Send connection requests to relevant people"""
        result = {
            "activity": "connection_requests",
            "count": 0,
            "errors": [],
            "requests_sent": []
        }
        
        if self.dry_run:
            simulated_count = min(max_count, random.randint(1, max_count))
            result["count"] = simulated_count
            result["requests_sent"] = [f"Simulated connection request {i+1}" for i in range(simulated_count)]
            logger.info(f"🧪 DRY RUN: Simulated {simulated_count} connection requests")
            return result
        
        from playwright.async_api import async_playwright
        
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
                
                # Navigate to "People You May Know" or search for relevant people
                await page.goto("https://www.linkedin.com/mynetwork/", timeout=self.timeout)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(3000)
                
                # Find potential connections
                connections = await self._find_potential_connections(page)
                logger.info(f"👥 Found {len(connections)} potential connections")
                
                # Send connection requests
                sent_count = 0
                for i, connection in enumerate(connections[:max_count]):
                    if not self._can_perform_more_actions():
                        logger.info("🛑 Daily action limit reached")
                        break
                    
                    try:
                        success = await self._send_single_connection_request(page, connection, i)
                        if success:
                            sent_count += 1
                            result["requests_sent"].append(f"Connection {i+1}")
                            self._increment_daily_action("connections")
                        
                        # Random delay between requests
                        await self._random_delay(10, 20)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to send connection request {i+1}: {e}")
                        result["errors"].append(f"Connection {i+1}: {str(e)}")
                
                result["count"] = sent_count
                
        except Exception as e:
            logger.error(f"❌ Error sending connection requests: {e}")
            result["errors"].append(str(e))
        finally:
            if browser:
                await browser.close()
        
        return result
    
    async def _find_potential_connections(self, page: Page) -> List[Any]:
        """Find potential connections on LinkedIn"""
        try:
            # Wait for connection suggestions to load
            await page.wait_for_selector('.mn-discovery-person-card, .discover-person-card', timeout=10000)
            
            # Get all person cards
            person_cards = await page.locator('.mn-discovery-person-card, .discover-person-card').all()
            
            relevant_connections = []
            for card in person_cards[:10]:  # Check first 10 suggestions
                try:
                    # Get person info
                    name_element = card.locator('.discover-person-card__name, .mn-discovery-person-card__name').first
                    headline_element = card.locator('.discover-person-card__occupation, .mn-discovery-person-card__occupation').first
                    
                    if await name_element.count() > 0 and await headline_element.count() > 0:
                        name = await name_element.text_content()
                        headline = await headline_element.text_content()
                        
                        if self._is_connection_relevant(headline):
                            relevant_connections.append(card)
                            if len(relevant_connections) >= 5:  # Limit to 5 relevant connections
                                break
                                
                except Exception as e:
                    logger.debug(f"Error processing connection card: {e}")
                    continue
            
            return relevant_connections
            
        except Exception as e:
            logger.error(f"❌ Error finding potential connections: {e}")
            return []
    
    def _is_connection_relevant(self, headline: str) -> bool:
        """Check if a potential connection is relevant"""
        if not headline:
            return False
        
        headline_lower = headline.lower()
        
        # Check for relevant professional terms
        relevant_terms = [
            'software engineer', 'developer', 'programmer', 'data scientist',
            'cybersecurity', 'ai engineer', 'machine learning', 'devops',
            'tech lead', 'python developer', 'full stack', 'backend',
            'frontend', 'security analyst', 'penetration tester'
        ]
        
        return any(term in headline_lower for term in relevant_terms)
    
    async def _send_single_connection_request(self, page: Page, connection_card, index: int) -> bool:
        """Send a connection request to a single person"""
        try:
            # Find connect button
            connect_button = connection_card.locator('button:has-text("Connect"), button[aria-label*="Connect"]').first
            
            if await connect_button.count() == 0:
                logger.debug(f"No connect button found for connection {index + 1}")
                return False
            
            # Click connect button
            await connect_button.click()
            await page.wait_for_timeout(2000)
            
            # Handle "Send without a note" or "Add a note" dialog
            send_button = page.locator('button:has-text("Send"), button:has-text("Send without a note")').first
            if await send_button.count() > 0:
                await send_button.click()
                await page.wait_for_timeout(1000)
                
                logger.info(f"🤝 Sent connection request {index + 1}")
                return True
            else:
                logger.warning(f"⚠️ Could not find send button for connection {index + 1}")
                return False
            
        except Exception as e:
            logger.warning(f"⚠️ Error sending connection request {index + 1}: {e}")
            return False
    
    def _can_perform_more_actions(self) -> bool:
        """Check if we can perform more actions today"""
        self._reset_daily_actions_if_new_day()
        return self.engagement_history["daily_actions"]["total"] < self.max_daily_actions
    
    def _increment_daily_action(self, action_type: str):
        """Increment daily action counter"""
        self.engagement_history["daily_actions"][action_type] += 1
        self.engagement_history["daily_actions"]["total"] += 1
        self.engagement_history["total_stats"][action_type] += 1
        self.engagement_history["total_stats"]["total"] += 1
        self._save_engagement_history()
    
    async def _random_delay(self, min_seconds: int = None, max_seconds: int = None):
        """Add random delay between actions"""
        if min_seconds is None:
            min_seconds = self.action_delay_min
        if max_seconds is None:
            max_seconds = self.action_delay_max
        
        delay = random.randint(min_seconds, max_seconds)
        logger.debug(f"⏱️ Waiting {delay} seconds...")
        await asyncio.sleep(delay)
    
    def _record_engagement_session(self, session_result: Dict[str, Any]):
        """Record engagement session in history"""
        try:
            engagement_summary = {
                "timestamp": session_result["timestamp"],
                "success": session_result["success"],
                "actions_performed": session_result["actions_performed"],
                "activities": session_result["activities"],
                "dry_run": session_result["dry_run"]
            }
            
            self.engagement_history["recent_engagements"].append(engagement_summary)
            
            # Keep only last 30 engagement sessions
            if len(self.engagement_history["recent_engagements"]) > 30:
                self.engagement_history["recent_engagements"] = self.engagement_history["recent_engagements"][-30:]
            
            self._save_engagement_history()
            
        except Exception as e:
            logger.error(f"❌ Error recording engagement session: {e}")
    
    def get_engagement_statistics(self) -> Dict[str, Any]:
        """Get engagement statistics"""
        self._reset_daily_actions_if_new_day()
        
        recent_sessions = [e for e in self.engagement_history["recent_engagements"] 
                          if datetime.fromisoformat(e["timestamp"]) > datetime.now() - timedelta(days=7)]
        
        return {
            "daily_actions": self.engagement_history["daily_actions"],
            "total_stats": self.engagement_history["total_stats"],
            "daily_limit": self.max_daily_actions,
            "recent_sessions_7d": len(recent_sessions),
            "recent_engagements": self.engagement_history["recent_engagements"][-5:]
        }

# Convenience functions
async def run_linkedin_engagement():
    """Simple function to run LinkedIn engagement"""
    manager = LinkedInEngagementManager()
    return await manager.run_daily_engagement()

# Example usage and testing
async def main():
    """Test the engagement manager"""
    try:
        manager = LinkedInEngagementManager()
        
        print("🤝 Testing LinkedIn Engagement Manager")
        print("=" * 50)
        
        # Show current statistics
        stats = manager.get_engagement_statistics()
        print(f"📊 Engagement Statistics:")
        print(f"  Daily Actions: {stats['daily_actions']['total']}/{stats['daily_limit']}")
        print(f"  Total Likes: {stats['total_stats']['likes']}")
        print(f"  Total Comments: {stats['total_stats']['comments']}")
        print(f"  Total Connections: {stats['total_stats']['connections']}")
        
        # Test engagement
        print(f"\n🧪 Testing daily engagement...")
        result = await manager.run_daily_engagement()
        
        print(f"\n📊 Engagement Result:")
        print(f"  Success: {result['success']}")
        print(f"  Actions Performed: {result['actions_performed']}")
        print(f"  Dry Run: {result['dry_run']}")
        
        if result['activities']:
            print(f"\n🎯 Activities:")
            for activity in result['activities']:
                print(f"  - {activity['activity'].replace('_', ' ').title()}: {activity['count']} actions")
        
        if result['errors']:
            print(f"\n❌ Errors:")
            for error in result['errors']:
                print(f"  - {error}")
        
        print("\n✅ Engagement manager test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
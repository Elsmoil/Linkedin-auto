# ai_modules/linkedin_reader.py
# ai_modules/linkedin_reader.py
import os
import asyncio
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Import our environment handler
try:
    from config.env_handler import env_handler
except ImportError:
    # Fallback if config module isn't available
    load_dotenv()
    env_handler = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInReader:
    def __init__(self):
        if env_handler:
            # Use environment handler for configuration
            ai_config = env_handler.get_ai_client_config()
            linkedin_config = env_handler.get_config('linkedin')
            
            self.api_key = ai_config['api_key']
            self.base_url = ai_config['base_url']
            self.li_email = linkedin_config['email']
            self.li_password = linkedin_config['password']
            self.li_cookie = linkedin_config['cookie']
            self.timeout = linkedin_config['timeout']
            self.headless = linkedin_config['headless']
        else:
            # Fallback to direct environment variables
            load_dotenv()
            self.api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
            self.base_url = os.getenv("OPENAI_API_BASE_URL", "https://openrouter.ai/api/v1")
            self.li_email = os.getenv("LINKEDIN_EMAIL")
            self.li_password = os.getenv("LINKEDIN_PASSWORD")
            self.li_cookie = os.getenv("LINKEDIN_COOKIE")
            self.timeout = int(os.getenv("LINKEDIN_TIMEOUT", "30000"))
            self.headless = os.getenv("LINKEDIN_HEADLESS", "true").lower() == "true"
        
        if not self.api_key:
            raise ValueError("❌ No AI API key found. Please configure OPENROUTER_API_KEY or OPENAI_API_KEY")
        
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_optimal_model(self, task_type: str) -> str:
        """Select the best AI model for specific tasks"""
        if env_handler:
            return env_handler.get_optimal_model(task_type)
        
        # Fallback model mapping
        model_map = {
            "analysis": "openai/gpt-4o",
            "writing": "anthropic/claude-3.5-sonnet", 
            "optimization": "openai/gpt-4o-mini",
            "cover_letter": "anthropic/claude-3.5-sonnet",
            "job_application": "openai/gpt-4o"
        }
        return model_map.get(task_type, "openai/gpt-4o")

    async def authenticate_linkedin(self, page: Page) -> bool:
        """Smart authentication with cookie fallback to email/password"""
        try:
            # Method 1: Try cookie authentication first
            if self.li_cookie:
                logger.info("🍪 Attempting cookie authentication...")
                await page.context.add_cookies([{
                    'name': 'li_at',
                    'value': self.li_cookie,
                    'domain': '.linkedin.com',
                    'path': '/'
                }])
                
                await page.goto("https://www.linkedin.com/feed", timeout=self.timeout)
                await page.wait_for_timeout(3000)
                
                # Check if cookie auth was successful
                if "feed" in page.url and "login" not in page.url:
                    logger.info("✅ Cookie authentication successful")
                    return True
                else:
                    logger.warning("⚠️ Cookie authentication failed, trying email/password...")
            
            # Method 2: Fallback to email/password
            if not self.li_email or not self.li_password:
                logger.error("❌ No LinkedIn credentials found")
                return False
                
            logger.info("🔐 Attempting email/password authentication...")
            await page.goto("https://www.linkedin.com/login", timeout=self.timeout)
            
            # Wait for login form to load
            await page.wait_for_selector('input[name="session_key"]', timeout=10000)
            
            # Fill login form
            await page.fill('input[name="session_key"]', self.li_email)
            await page.fill('input[name="session_password"]', self.li_password)
            await page.click('button[type="submit"]')
            
            # Wait for successful login or handle challenges
            try:
                await page.wait_for_url("**/feed/**", timeout=15000)
                logger.info("✅ Email/password authentication successful")
                return True
            except:
                # Check for security challenges
                current_url = page.url
                if "challenge" in current_url or "security" in current_url:
                    logger.warning("🛡️ Security challenge detected - manual intervention may be needed")
                    # Wait a bit longer for manual intervention
                    try:
                        await page.wait_for_url("**/feed/**", timeout=60000)
                        logger.info("✅ Authentication completed after security challenge")
                        return True
                    except:
                        logger.error("❌ Failed to complete authentication after security challenge")
                        return False
                
                logger.error("❌ Authentication failed - login unsuccessful")
                return False
                
        except Exception as e:
            logger.error(f"❌ Authentication failed with error: {e}")
            return False

    async def get_profile_html(self) -> Optional[str]:
        """Fetch LinkedIn profile HTML with smart authentication"""
        browser = None
        try:
            async with async_playwright() as p:
                # Launch browser with appropriate settings
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security'
                    ]
                )
                
                # Create context with realistic settings
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1366, 'height': 768},
                    locale='en-US'
                )
                
                page = await context.new_page()
                
                # Authenticate
                if not await self.authenticate_linkedin(page):
                    logger.error("❌ Failed to authenticate with LinkedIn")
                    return None
                
                # Navigate to profile
                logger.info("📄 Fetching profile page...")
                await page.goto("https://www.linkedin.com/in/me", timeout=self.timeout)
                await page.wait_for_load_state("networkidle", timeout=30000)
                
                # Wait for profile content to load
                try:
                    await page.wait_for_selector('[data-section="summary"], .artdeco-card, .profile-section', timeout=10000)
                except:
                    logger.warning("⚠️ Profile sections not fully loaded, continuing anyway...")
                
                await page.wait_for_timeout(3000)
                
                # Get page content
                html = await page.content()
                logger.info("✅ Profile HTML fetched successfully")
                return html
                
        except Exception as e:
            logger.error(f"❌ Error fetching profile: {e}")
            return None
        finally:
            if browser:
                await browser.close()

    async def ask_ai_to_analyze(self, html: str, task_type: str = "analysis") -> Optional[str]:
        """Analyze LinkedIn profile with optimal AI model"""
        if not html:
            logger.error("❌ No HTML content provided")
            return None
            
        try:
            model = self.get_optimal_model(task_type)
            logger.info(f"🤖 Using model: {model} for task: {task_type}")
            
            # Enhanced prompt with better structure
            notes = """
            User Profile Notes:
            - ALX Software Engineering & AI Program Graduate
            - Skills: Python, Linux, Networking, Penetration Testing, Cybersecurity
            - Certifications: Cisco Computer Basics + others in posts
            - Interests: Software Engineering, AI, Cybersecurity
            - GitHub: https://github.com/Elsmoil
            """

            prompt = f"""
            You are a LinkedIn profile optimization expert. Analyze the profile and provide improvements.

            HTML Content (truncated for analysis):
            {html[:4000]}...

            {notes}

            Please provide a structured analysis:

            ## CURRENT PROFILE ANALYSIS
            1. **Current Headline:** [Extract from HTML or state if not found]
            2. **Current Summary:** [Extract from HTML or state if not found]
            3. **Current Skills:** [List found skills or state if not found]

            ## OPTIMIZED RECOMMENDATIONS
            
            ### **Improved Headline:**
            [Write a compelling, keyword-rich headline that highlights Software Engineering, AI, and Cybersecurity expertise]

            ### **Improved Summary:**
            [Write a professional 2-3 paragraph summary that tells a compelling story and includes relevant keywords]

            ### **Skills Optimization:**
            [List 10 most relevant skills in priority order based on the user's background]

            ### **Additional Recommendations:**
            - [Specific suggestions for improving profile visibility]
            - [Content strategy recommendations]
            - [Networking suggestions]

            Format the response clearly with markdown headers and bullet points.
            Keep suggestions practical and actionable.
            """

            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2500,
                temperature=0.7,
            )

            result = response.choices[0].message.content
            logger.info("✅ AI analysis completed successfully")
            return result

        except Exception as e:
            logger.error(f"❌ AI analysis failed: {e}")
            return None

    async def generate_content(self, content_type: str, context: str = "") -> Optional[str]:
        """Generate various types of LinkedIn content"""
        model = self.get_optimal_model("writing")
        
        prompts = {
            "post": f"Write an engaging LinkedIn post about: {context}. Make it professional but conversational, include relevant hashtags.",
            "comment": f"Write a thoughtful, engaging comment for this LinkedIn post: {context}",
            "message": f"Write a professional LinkedIn connection message for: {context}",
            "headline": f"Create a compelling LinkedIn headline for someone with this background: {context}"
        }
        
        if content_type not in prompts:
            logger.error(f"❌ Unknown content type: {content_type}")
            return None
            
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompts[content_type]}],
                max_tokens=800,
                temperature=0.8,
            )
            
            result = response.choices[0].message.content
            logger.info(f"✅ {content_type} content generated successfully")
            return result
            
        except Exception as e:
            logger.error(f"❌ Content generation failed: {e}")
            return None

# Backward compatibility functions
async def get_profile_html():
    """Legacy function for backward compatibility"""
    reader = LinkedInReader()
    return await reader.get_profile_html()

async def ask_ai_to_analyze(html: str):
    """Legacy function for backward compatibility"""
    reader = LinkedInReader()
    return await reader.ask_ai_to_analyze(html)

# Example usage and testing
async def main():
    """Test the LinkedIn reader functionality"""
    try:
        reader = LinkedInReader()
        
        print("🚀 Starting LinkedIn profile analysis...")
        
        # Fetch profile
        html = await reader.get_profile_html()
        if not html:
            print("❌ Failed to fetch profile")
            return
        
        # Analyze profile
        analysis = await reader.ask_ai_to_analyze(html, "analysis")
        if analysis:
            print("\n📊 Profile Analysis:")
            print("=" * 60)
            print(analysis)
        else:
            print("❌ Analysis failed")
            
    except Exception as e:
        logger.error(f"❌ Main execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
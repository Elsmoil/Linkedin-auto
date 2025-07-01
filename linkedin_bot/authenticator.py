# linkedin_bot/authenticator.py
import asyncio
import logging
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from playwright.async_api import Page, BrowserContext
from datetime import datetime, timedelta

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

class LinkedInAuthenticator:
    """Advanced LinkedIn authentication with multiple fallback methods"""
    
    def __init__(self):
        self._load_config()
        self._initialize_session_manager()
        
    def _load_config(self):
        """Load authentication configuration"""
        if env_handler:
            linkedin_config = env_handler.get_config('linkedin')
            self.email = linkedin_config.get('email')
            self.password = linkedin_config.get('password')
            self.cookie = linkedin_config.get('cookie')
            self.timeout = linkedin_config.get('timeout', 30000)
            self.headless = linkedin_config.get('headless', True)
        else:
            # Fallback to environment variables
            self.email = os.getenv("LINKEDIN_EMAIL")
            self.password = os.getenv("LINKEDIN_PASSWORD")
            self.cookie = os.getenv("LINKEDIN_COOKIE")
            self.timeout = int(os.getenv("LINKEDIN_TIMEOUT", "30000"))
            self.headless = os.getenv("LINKEDIN_HEADLESS", "true").lower() == "true"
        
        self.session_file = Path("logs/linkedin_session.json")
        self.session_file.parent.mkdir(exist_ok=True)
        
    def _initialize_session_manager(self):
        """Initialize session management"""
        self.session_data = self._load_session_data()
        
    def _load_session_data(self) -> Dict[str, Any]:
        """Load existing session data"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                logger.info("✅ Loaded existing session data")
                return data
            except Exception as e:
                logger.warning(f"⚠️ Failed to load session data: {e}")
        
        return {
            "created_at": datetime.now().isoformat(),
            "last_successful_auth": None,
            "auth_method": None,
            "failed_attempts": 0,
            "cookies": None,
            "user_agent": None,
            "session_valid_until": None
        }
    
    def _save_session_data(self):
        """Save session data to file"""
        try:
            with open(self.session_file, 'w') as f:
                json.dump(self.session_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save session data: {e}")
    
    async def authenticate(self, page: Page) -> Dict[str, Any]:
        """Main authentication method with intelligent fallback"""
        auth_result = {
            "success": False,
            "method": None,
            "message": "",
            "timestamp": datetime.now().isoformat(),
            "requires_manual_intervention": False
        }
        
        try:
            # Method 1: Try saved session cookies
            if await self._try_session_cookies(page):
                auth_result.update({
                    "success": True,
                    "method": "session_cookies",
                    "message": "Authenticated using saved session cookies"
                })
                self._update_successful_auth("session_cookies")
                return auth_result
            
            # Method 2: Try li_at cookie
            if self.cookie and await self._try_li_at_cookie(page):
                auth_result.update({
                    "success": True,
                    "method": "li_at_cookie",
                    "message": "Authenticated using li_at cookie"
                })
                await self._save_session_cookies(page)
                self._update_successful_auth("li_at_cookie")
                return auth_result
            
            # Method 3: Try email/password login
            if self.email and self.password:
                login_result = await self._try_email_password_login(page)
                if login_result["success"]:
                    auth_result.update({
                        "success": True,
                        "method": "email_password",
                        "message": login_result["message"]
                    })
                    await self._save_session_cookies(page)
                    self._update_successful_auth("email_password")
                    return auth_result
                else:
                    auth_result.update({
                        "message": login_result["message"],
                        "requires_manual_intervention": login_result.get("requires_manual_intervention", False)
                    })
            
            # All methods failed
            self.session_data["failed_attempts"] += 1
            self._save_session_data()
            
            auth_result["message"] = "All authentication methods failed"
            logger.error("❌ All authentication methods failed")
            
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            auth_result["message"] = f"Authentication error: {str(e)}"
        
        return auth_result
    
    async def _try_session_cookies(self, page: Page) -> bool:
        """Try authentication using saved session cookies"""
        try:
            if not self.session_data.get("cookies"):
                return False
            
            # Check if session is still valid
            if self.session_data.get("session_valid_until"):
                valid_until = datetime.fromisoformat(self.session_data["session_valid_until"])
                if datetime.now() > valid_until:
                    logger.info("🕒 Saved session expired")
                    return False
            
            logger.info("🍪 Trying saved session cookies...")
            
            # Add saved cookies to context
            await page.context.add_cookies(self.session_data["cookies"])
            
            # Test if cookies work
            await page.goto("https://www.linkedin.com/feed", timeout=self.timeout)
            await page.wait_for_timeout(3000)
            
            if await self._verify_authentication(page):
                logger.info("✅ Session cookies authentication successful")
                return True
            else:
                logger.info("❌ Session cookies invalid, clearing saved session")
                self.session_data["cookies"] = None
                self._save_session_data()
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Session cookies authentication failed: {e}")
            return False
    
    async def _try_li_at_cookie(self, page: Page) -> bool:
        """Try authentication using li_at cookie"""
        try:
            logger.info("🍪 Trying li_at cookie authentication...")
            
            # Add li_at cookie
            await page.context.add_cookies([{
                'name': 'li_at',
                'value': self.cookie,
                'domain': '.linkedin.com',
                'path': '/'
            }])
            
            # Navigate to LinkedIn
            await page.goto("https://www.linkedin.com/feed", timeout=self.timeout)
            await page.wait_for_timeout(3000)
            
            if await self._verify_authentication(page):
                logger.info("✅ li_at cookie authentication successful")
                return True
            else:
                logger.warning("❌ li_at cookie authentication failed")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ li_at cookie authentication failed: {e}")
            return False
    
    async def _try_email_password_login(self, page: Page) -> Dict[str, Any]:
        """Try authentication using email and password"""
        result = {
            "success": False,
            "message": "",
            "requires_manual_intervention": False
        }
        
        try:
            logger.info("🔐 Trying email/password authentication...")
            
            # Navigate to login page
            await page.goto("https://www.linkedin.com/login", timeout=self.timeout)
            await page.wait_for_selector('input[name="session_key"]', timeout=10000)
            
            # Fill login form
            await page.fill('input[name="session_key"]', self.email)
            await page.wait_for_timeout(1000)
            
            await page.fill('input[name="session_password"]', self.password)
            await page.wait_for_timeout(1000)
            
            # Submit form
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(5000)
            
            # Handle different post-login scenarios
            current_url = page.url
            
            # Check for successful login
            if "feed" in current_url or "in/" in current_url:
                result.update({
                    "success": True,
                    "message": "Email/password authentication successful"
                })
                logger.info("✅ Email/password authentication successful")
                return result
            
            # Check for security challenge
            if await self._handle_security_challenge(page):
                if await self._verify_authentication(page):
                    result.update({
                        "success": True,
                        "message": "Authentication successful after security challenge"
                    })
                    return result
            
            # Check for CAPTCHA
            if await page.locator('iframe[src*="captcha"], [data-test-id="captcha"]').count() > 0:
                logger.warning("🤖 CAPTCHA detected")
                result.update({
                    "message": "CAPTCHA detected - manual intervention required",
                    "requires_manual_intervention": True
                })
                return result
            
            # Check for verification code
            if await page.locator('input[name="pin"], input[id*="verification"]').count() > 0:
                logger.warning("📱 Verification code required")
                result.update({
                    "message": "Verification code required - manual intervention needed",
                    "requires_manual_intervention": True
                })
                return result
            
            # Check for error messages
            error_selectors = [
                '.form__label--error',
                '.alert',
                '[data-test-id="sign-in-error"]',
                '.login-form__error-message'
            ]
            
            for selector in error_selectors:
                if await page.locator(selector).count() > 0:
                    error_text = await page.locator(selector).first.text_content()
                    result["message"] = f"Login error: {error_text}"
                    logger.warning(f"⚠️ Login error: {error_text}")
                    return result
            
            # Generic failure
            result["message"] = "Login failed - unknown reason"
            logger.warning("❌ Email/password authentication failed - unknown reason")
            
        except Exception as e:
            result["message"] = f"Login exception: {str(e)}"
            logger.error(f"❌ Email/password authentication error: {e}")
        
        return result
    
    async def _handle_security_challenge(self, page: Page) -> bool:
        """Handle LinkedIn security challenges"""
        try:
            # Wait for challenge elements to appear
            challenge_selectors = [
                '[data-test-id="challenge-form"]',
                '.challenge-page',
                'h1:has-text("Security Verification")',
                'h1:has-text("Help us protect")'
            ]
            
            challenge_detected = False
            for selector in challenge_selectors:
                if await page.locator(selector).count() > 0:
                    challenge_detected = True
                    break
            
            if not challenge_detected:
                return False
            
            logger.warning("🛡️ Security challenge detected")
            
            # Check for different types of challenges
            
            # Email verification
            if await page.locator('input[type="email"], input[name="email"]').count() > 0:
                logger.info("📧 Email verification challenge")
                # For now, just wait and hope user handles it manually
                await page.wait_for_timeout(30000)  # Wait 30 seconds
                return True
            
            # Phone verification
            if await page.locator('input[type="tel"], input[name="phone"]').count() > 0:
                logger.info("📱 Phone verification challenge")
                await page.wait_for_timeout(30000)  # Wait 30 seconds
                return True
            
            # Generic challenge - wait for user intervention
            logger.info("⏳ Waiting for manual security challenge completion...")
            
            # Wait up to 2 minutes for challenge to be resolved
            for i in range(24):  # 24 * 5 seconds = 2 minutes
                await page.wait_for_timeout(5000)
                if "feed" in page.url or "in/" in page.url:
                    logger.info("✅ Security challenge resolved")
                    return True
            
            logger.warning("⏰ Security challenge timeout")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error handling security challenge: {e}")
            return False
    
    async def _verify_authentication(self, page: Page) -> bool:
        """Verify that we are successfully authenticated"""
        try:
            current_url = page.url
            
            # Check URL patterns that indicate successful authentication
            authenticated_patterns = [
                "linkedin.com/feed",
                "linkedin.com/in/",
                "linkedin.com/mynetwork",
                "linkedin.com/messaging"
            ]
            
            for pattern in authenticated_patterns:
                if pattern in current_url:
                    return True
            
            # Check for specific authenticated elements
            authenticated_selectors = [
                '.global-nav__me',
                '[data-test-id="nav-me-button"]',
                '.nav-item__profile-member-photo',
                '[aria-label="Me"]'
            ]
            
            for selector in authenticated_selectors:
                if await page.locator(selector).count() > 0:
                    return True
            
            # Check if we're NOT on login page
            if "login" not in current_url and "challenge" not in current_url:
                # Try to access a protected endpoint
                try:
                    await page.goto("https://www.linkedin.com/in/me", timeout=10000)
                    await page.wait_for_timeout(2000)
                    if "login" not in page.url:
                        return True
                except:
                    pass
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error verifying authentication: {e}")
            return False
    
    async def _save_session_cookies(self, page: Page):
        """Save current session cookies for future use"""
        try:
            cookies = await page.context.cookies()
            
            # Filter for important LinkedIn cookies
            important_cookies = []
            important_names = ['li_at', 'JSESSIONID', 'liap', 'li_mc', 'bcookie', 'bscookie']
            
            for cookie in cookies:
                if any(name in cookie['name'] for name in important_names) or 'linkedin.com' in cookie['domain']:
                    important_cookies.append(cookie)
            
            if important_cookies:
                self.session_data["cookies"] = important_cookies
                self.session_data["session_valid_until"] = (datetime.now() + timedelta(days=7)).isoformat()
                self.session_data["user_agent"] = await page.evaluate("navigator.userAgent")
                self._save_session_data()
                logger.info(f"✅ Saved {len(important_cookies)} session cookies")
            
        except Exception as e:
            logger.error(f"❌ Error saving session cookies: {e}")
    
    def _update_successful_auth(self, method: str):
        """Update session data after successful authentication"""
        self.session_data["last_successful_auth"] = datetime.now().isoformat()
        self.session_data["auth_method"] = method
        self.session_data["failed_attempts"] = 0
        self._save_session_data()
    
    def get_auth_status(self) -> Dict[str, Any]:
        """Get current authentication status"""
        return {
            "has_credentials": bool(self.email and self.password),
            "has_cookie": bool(self.cookie),
            "has_saved_session": bool(self.session_data.get("cookies")),
            "last_successful_auth": self.session_data.get("last_successful_auth"),
            "auth_method": self.session_data.get("auth_method"),
            "failed_attempts": self.session_data.get("failed_attempts", 0),
            "session_valid_until": self.session_data.get("session_valid_until")
        }
    
    def clear_session(self):
        """Clear saved session data"""
        self.session_data = {
            "created_at": datetime.now().isoformat(),
            "last_successful_auth": None,
            "auth_method": None,
            "failed_attempts": 0,
            "cookies": None,
            "user_agent": None,
            "session_valid_until": None
        }
        self._save_session_data()
        logger.info("🗑️ Cleared saved session data")

# Convenience functions for backward compatibility
async def authenticate_linkedin(page: Page) -> bool:
    """Legacy function for backward compatibility"""
    authenticator = LinkedInAuthenticator()
    result = await authenticator.authenticate(page)
    return result["success"]

# Example usage and testing
async def main():
    """Test the authenticator"""
    from playwright.async_api import async_playwright
    
    try:
        authenticator = LinkedInAuthenticator()
        
        print("🔐 Testing LinkedIn Authenticator")
        print("=" * 50)
        
        # Show auth status
        status = authenticator.get_auth_status()
        print(f"📊 Authentication Status:")
        print(f"  Has Credentials: {status['has_credentials']}")
        print(f"  Has Cookie: {status['has_cookie']}")
        print(f"  Has Saved Session: {status['has_saved_session']}")
        print(f"  Last Auth: {status['last_successful_auth']}")
        print(f"  Failed Attempts: {status['failed_attempts']}")
        
        # Test authentication
        if status['has_credentials'] or status['has_cookie']:
            print(f"\n🧪 Testing authentication...")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=authenticator.headless)
                context = await browser.new_context()
                page = await context.new_page()
                
                result = await authenticator.authenticate(page)
                
                print(f"\n📊 Authentication Result:")
                print(f"  Success: {result['success']}")
                print(f"  Method: {result['method']}")
                print(f"  Message: {result['message']}")
                print(f"  Manual Intervention: {result['requires_manual_intervention']}")
                
                await browser.close()
        else:
            print("⚠️ No credentials available for testing")
        
        print("\n✅ Authenticator test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
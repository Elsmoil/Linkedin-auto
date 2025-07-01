import asyncio
import logging
import json
import os
import random
from typing import Optional, Dict, Any, List
from pathlib import Path
from playwright.async_api import Page, BrowserContext
from datetime import datetime, timedelta

# Configure logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import our modules with better error handling
env_handler = None
LinkedInAuthenticator = None
LinkedInJobScraper = None
LinkedInPerformanceTracker = None
LinkedInReader = None
LinkedInContentGenerator = None

try:
    from config.env_handler import env_handler
    logger.info("✅ Imported env_handler")
except ImportError as e:
    logger.warning(f"⚠️ Could not import env_handler: {e}")
    from dotenv import load_dotenv
    load_dotenv()

try:
    from .authenticator import LinkedInAuthenticator
    logger.info("✅ Imported LinkedInAuthenticator")
except ImportError as e:
    logger.warning(f"⚠️ Could not import LinkedInAuthenticator: {e}")
    try:
        # Try absolute import
        from linkedin_bot.authenticator import LinkedInAuthenticator
        logger.info("✅ Imported LinkedInAuthenticator (absolute)")
    except ImportError:
        logger.error("❌ Could not import LinkedInAuthenticator at all")

try:
    from .job_scraper import LinkedInJobScraper
    logger.info("✅ Imported LinkedInJobScraper")
except ImportError as e:
    logger.warning(f"⚠️ Could not import LinkedInJobScraper: {e}")

try:
    from analytics.performance_tracker import LinkedInPerformanceTracker
    logger.info("✅ Imported LinkedInPerformanceTracker")
except ImportError as e:
    logger.warning(f"⚠️ Could not import LinkedInPerformanceTracker: {e}")

try:
    from ai_modules.linkedin_reader import LinkedInReader
    logger.info("✅ Imported LinkedInReader")
except ImportError as e:
    logger.warning(f"⚠️ Could not import LinkedInReader: {e}")

try:
    from content_generator import LinkedInContentGenerator
    logger.info("✅ Imported LinkedInContentGenerator")
except ImportError as e:
    logger.warning(f"⚠️ Could not import LinkedInContentGenerator: {e}")

class LinkedInApplicationManager:
    """Advanced LinkedIn job application automation with AI-powered cover letters and smart filtering"""
    
    def __init__(self):
        # Initialize components with error handling
        try:
            if LinkedInAuthenticator:
                self.authenticator = LinkedInAuthenticator()
                logger.info("✅ Initialized LinkedInAuthenticator")
            else:
                raise ImportError("LinkedInAuthenticator not available")
        except Exception as e:
            logger.error(f"❌ Failed to initialize LinkedInAuthenticator: {e}")
            raise
        
        # Optional components - initialize if available
        try:
            self.job_scraper = LinkedInJobScraper() if LinkedInJobScraper else None
            if self.job_scraper:
                logger.info("✅ Initialized LinkedInJobScraper")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize LinkedInJobScraper: {e}")
            self.job_scraper = None
        
        try:
            self.performance_tracker = LinkedInPerformanceTracker() if LinkedInPerformanceTracker else None
            if self.performance_tracker:
                logger.info("✅ Initialized LinkedInPerformanceTracker")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize LinkedInPerformanceTracker: {e}")
            self.performance_tracker = None
        
        try:
            self.linkedin_reader = LinkedInReader() if LinkedInReader else None
            if self.linkedin_reader:
                logger.info("✅ Initialized LinkedInReader")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize LinkedInReader: {e}")
            self.linkedin_reader = None
        
        try:
            self.content_generator = LinkedInContentGenerator() if LinkedInContentGenerator else None
            if self.content_generator:
                logger.info("✅ Initialized LinkedInContentGenerator")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize LinkedInContentGenerator: {e}")
            self.content_generator = None
        
        # Initialize configuration and tracking
        self._load_config()
        self._initialize_application_tracking()
        
    def _load_config(self):
        """Load application manager configuration"""
        try:
            if env_handler:
                linkedin_config = env_handler.get_config('linkedin')
                self.timeout = linkedin_config.get('timeout', 30000)
                
                # Application configuration
                app_config = env_handler.get_config('job_applications')
                self.max_daily_applications = app_config.get('max_daily_applications', 10)
                self.auto_apply_enabled = app_config.get('auto_apply_enabled', False)
                self.cv_path = app_config.get('cv_path', './cv/resume.pdf')
                self.cover_letter_template = app_config.get('cover_letter_template', '')
                self.apply_delay_min = app_config.get('apply_delay_min', 120)  # 2 minutes
                self.apply_delay_max = app_config.get('apply_delay_max', 300)  # 5 minutes
            else:
                # Fallback to environment variables
                self.timeout = int(os.getenv('LINKEDIN_TIMEOUT', '30000'))
                self.max_daily_applications = int(os.getenv('MAX_DAILY_APPLICATIONS', '10'))
                self.auto_apply_enabled = os.getenv('AUTO_APPLY_ENABLED', 'false').lower() == 'true'
                self.cv_path = os.getenv('CV_PATH', './cv/resume.pdf')
                self.cover_letter_template = os.getenv('COVER_LETTER_TEMPLATE', '')
                self.apply_delay_min = int(os.getenv('APPLY_DELAY_MIN', '120'))
                self.apply_delay_max = int(os.getenv('APPLY_DELAY_MAX', '300'))
            
            # Ensure CV directory exists
            cv_path = Path(self.cv_path)
            cv_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not cv_path.exists():
                logger.warning(f"⚠️ CV file not found at {self.cv_path}")
                # Create a placeholder CV file
                with open(cv_path, 'w') as f:
                    f.write("Placeholder CV - Please replace with your actual CV")
            
            self.applications_file = Path("logs/job_applications.json")
            self.applications_file.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info("✅ Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Error loading configuration: {e}")
            # Set default values
            self.timeout = 30000
            self.max_daily_applications = 10
            self.auto_apply_enabled = False
            self.cv_path = './cv/resume.pdf'
            self.cover_letter_template = ''
            self.apply_delay_min = 120
            self.apply_delay_max = 300
        
    def _initialize_application_tracking(self):
        """Initialize application tracking"""
        try:
            self.applications_data = self._load_applications_data()
            logger.info("✅ Application tracking initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing application tracking: {e}")
            self.applications_data = {
                "created_at": datetime.now().isoformat(),
                "total_applications": 0,
                "applications": [],
                "daily_counts": {},
                "success_rate": 0.0,
                "blacklisted_companies": [],
                "preferred_companies": []
            }
        
    def _load_applications_data(self) -> Dict[str, Any]:
        """Load previous application data"""
        if self.applications_file.exists():
            try:
                with open(self.applications_file, 'r') as f:
                    data = json.load(f)
                logger.info("✅ Loaded job applications history")
                return data
            except Exception as e:
                logger.warning(f"⚠️ Failed to load applications data: {e}")
        
        return {
            "created_at": datetime.now().isoformat(),
            "total_applications": 0,
            "applications": [],
            "daily_counts": {},
            "success_rate": 0.0,
            "blacklisted_companies": [],
            "preferred_companies": []
        }
    
    def _save_applications_data(self):
        """Save applications data to file"""
        try:
            with open(self.applications_file, 'w') as f:
                json.dump(self.applications_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save applications data: {e}")
    
    async def apply_to_job(self, job_data: Dict[str, Any], cv_path: Optional[str] = None, 
                          cover_letter: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """Apply to a specific job with AI-generated cover letter"""
        
        result = {
            "success": False,
            "job_id": job_data.get("id", "unknown"),
            "job_title": job_data.get("title", "Unknown"),
            "company": job_data.get("company", "Unknown"),
            "timestamp": datetime.now().isoformat(),
            "application_method": "linkedin_easy_apply",
            "cv_used": cv_path or self.cv_path,
            "cover_letter_generated": False,
            "cover_letter_content": "",
            "error": "",
            "application_steps": [],
            "dry_run": dry_run
        }
        
        try:
            # Check if already applied
            job_id = job_data.get("id")
            if isinstance(job_id, str) and job_id:
                if self._has_already_applied(job_id):
                    result["error"] = "Already applied to this job"
                    return result
            elif job_id is None:
                result["error"] = "Job ID is missing"
                return result
            
            # Check daily limit
            if self._has_reached_daily_limit():
                result["error"] = f"Daily application limit reached ({self.max_daily_applications})"
                return result
            
            # Check if company is blacklisted
            if self._is_company_blacklisted(job_data.get("company", "")):
                result["error"] = "Company is blacklisted"
                return result
            
            # Check if authenticator is available
            if not hasattr(self, 'authenticator') or not self.authenticator:
                result["error"] = "LinkedIn authenticator not available"
                return result
            
            from playwright.async_api import async_playwright
            
            browser = None
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=getattr(self.authenticator, 'headless', True),
                        args=['--no-sandbox', '--disable-dev-shm-usage']
                    )
                    context = await browser.new_context()
                    page = await context.new_page()
                    
                    # Authenticate
                    auth_result = await self.authenticator.authenticate(page)
                    if not auth_result["success"]:
                        result["error"] = f"Authentication failed: {auth_result['message']}"
                        return result
                    
                    # Navigate to job page
                    job_url = job_data.get("url", "")
                    if not job_url:
                        result["error"] = "No job URL provided"
                        return result
                    
                    result["application_steps"].append("Navigating to job page")
                    await page.goto(job_url, timeout=self.timeout)
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(3)
                    
                    # Check if Easy Apply is available
                    easy_apply_button = page.locator('button:has-text("Easy Apply"), .jobs-apply-button')
                    if await easy_apply_button.count() == 0:
                        result["error"] = "Easy Apply not available for this job"
                        result["application_method"] = "external_redirect"
                        return result
                    
                    # Generate cover letter if not provided
                    if not cover_letter:
                        result["application_steps"].append("Generating cover letter")
                        cover_letter = await self._generate_cover_letter(job_data)
                        result["cover_letter_generated"] = True
                        result["cover_letter_content"] = cover_letter
                    
                    if dry_run:
                        result["success"] = True
                        result["application_steps"].append("DRY RUN - Application simulation completed")
                        logger.info(f"🧪 DRY RUN: Would apply to {job_data.get('title')} at {job_data.get('company')}")
                        return result
                    
                    # Proceed with actual application
                    result["application_steps"].append("Starting Easy Apply process")
                    application_result = await self._complete_easy_apply_process(
                        page, job_data, cv_path or self.cv_path, cover_letter
                    )
                    
                    if application_result["success"]:
                        result["success"] = True
                        result["application_steps"].extend(application_result["steps"])
                        
                        # Record application
                        self._record_application(job_data, result)
                        
                        # Track in performance tracker if available
                        if self.performance_tracker:
                            try:
                                self.performance_tracker.track_job_application(
                                    company=job_data.get("company", ""),
                                    position=job_data.get("title", ""),
                                    location=job_data.get("location", ""),
                                    cv_version=Path(result["cv_used"]).name,
                                    cover_letter_used=True,
                                    source_url=job_url
                                )
                            except Exception as e:
                                logger.warning(f"⚠️ Could not track application: {e}")
                        
                        logger.info(f"✅ Successfully applied to {job_data.get('title')} at {job_data.get('company')}")
                    else:
                        result["error"] = application_result["error"]
                        result["application_steps"].extend(application_result["steps"])
                    
            except Exception as e:
                logger.error(f"❌ Error applying to job: {e}")
                result["error"] = str(e)
            finally:
                if browser:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"❌ Outer error applying to job: {e}")
            result["error"] = str(e)
        
        return result
    
    async def _complete_easy_apply_process(self, page: Page, job_data: Dict[str, Any], 
                                         cv_path: str, cover_letter: str) -> Dict[str, Any]:
        """Complete the LinkedIn Easy Apply process"""
        
        result = {
            "success": False,
            "steps": [],
            "error": ""
        }
        
        try:
            # Click Easy Apply button
            easy_apply_button = page.locator('button:has-text("Easy Apply"), .jobs-apply-button').first
            await easy_apply_button.click()
            result["steps"].append("Clicked Easy Apply button")
            await asyncio.sleep(2)
            
            # Handle multi-step application process
            max_steps = 5
            current_step = 0
            
            while current_step < max_steps:
                current_step += 1
                result["steps"].append(f"Processing application step {current_step}")
                
                # Check for file upload (CV/Resume)
                file_input = page.locator('input[type="file"]')
                if await file_input.count() > 0 and cv_path and Path(cv_path).exists():
                    await file_input.set_input_files(cv_path)
                    result["steps"].append("Uploaded CV/Resume")
                    await asyncio.sleep(2)
                
                # Check for cover letter text area
                cover_letter_field = page.locator('textarea[name*="cover"], textarea[id*="cover"], textarea:has-text("cover letter")')
                if await cover_letter_field.count() > 0 and cover_letter:
                    await cover_letter_field.fill(cover_letter[:2000])  # LinkedIn limit
                    result["steps"].append("Added cover letter")
                    await asyncio.sleep(1)
                
                # Fill any text inputs (questions)
                text_inputs = await page.locator('input[type="text"]:visible, textarea:visible').all()
                for input_field in text_inputs:
                    try:
                        placeholder = await input_field.get_attribute("placeholder") or ""
                        aria_label = await input_field.get_attribute("aria-label") or ""
                        
                        # Smart field filling based on common questions
                        if any(keyword in (placeholder + aria_label).lower() for keyword in ["experience", "years"]):
                            await input_field.fill("2")
                        elif any(keyword in (placeholder + aria_label).lower() for keyword in ["salary", "compensation"]):
                            await input_field.fill("Negotiable")
                        elif any(keyword in (placeholder + aria_label).lower() for keyword in ["website", "portfolio"]):
                            await input_field.fill("https://github.com/yourusername")
                        elif any(keyword in (placeholder + aria_label).lower() for keyword in ["phone", "mobile"]):
                            await input_field.fill("+1-555-0123")  # You should use real number
                        
                        await asyncio.sleep(0.5)
                    except:
                        continue
                
                # Handle dropdowns/select fields
                select_elements = await page.locator('select:visible').all()
                for select_elem in select_elements:
                    try:
                        options = await select_elem.locator('option').all()
                        if len(options) > 1:
                            # Select the first non-empty option
                            await select_elem.select_option(index=1)
                        await asyncio.sleep(0.5)
                    except:
                        continue
                
                # Handle radio buttons (Yes/No questions)
                radio_groups = await page.locator('input[type="radio"]:visible').all()
                processed_groups = set()
                
                for radio in radio_groups:
                    try:
                        name = await radio.get_attribute("name")
                        if name and name not in processed_groups:
                            # Generally select "Yes" for authorization questions
                            yes_radio = page.locator(f'input[name="{name}"][value*="yes"], input[name="{name}"][value="true"]').first
                            if await yes_radio.count() > 0:
                                await yes_radio.click()
                            else:
                                # Default to first option
                                await radio.click()
                            processed_groups.add(name)
                            await asyncio.sleep(0.5)
                    except:
                        continue
                
                # Check for Next/Continue button
                next_button = page.locator('button:has-text("Next"), button:has-text("Continue"), button[aria-label*="next"]')
                if await next_button.count() > 0:
                    await next_button.first.click()
                    result["steps"].append(f"Clicked Next button (step {current_step})")
                    await asyncio.sleep(3)
                    continue
                
                # Check for Review button
                review_button = page.locator('button:has-text("Review"), button:has-text("Review application")')
                if await review_button.count() > 0:
                    await review_button.first.click()
                    result["steps"].append("Clicked Review button")
                    await asyncio.sleep(3)
                    continue
                
                # Check for Submit button
                submit_button = page.locator('button:has-text("Submit"), button:has-text("Submit application")')
                if await submit_button.count() > 0:
                    await submit_button.first.click()
                    result["steps"].append("Clicked Submit button")
                    await asyncio.sleep(5)
                    
                    # Verify submission success
                    success_indicators = [
                        'text="Application sent"',
                        'text="Your application was sent"',
                        'text="Application submitted"',
                        '[class*="success"]',
                        '[class*="confirmation"]'
                    ]
                    
                    for indicator in success_indicators:
                        if await page.locator(indicator).count() > 0:
                            result["success"] = True
                            result["steps"].append("Application submitted successfully")
                            break
                    
                    break
                
                # Check for Close/Done button (sometimes appears after submission)
                close_button = page.locator('button:has-text("Done"), button:has-text("Close"), button[aria-label*="close"]')
                if await close_button.count() > 0:
                    result["success"] = True
                    result["steps"].append("Application process completed")
                    break
                
                # If no buttons found, we might be done or stuck
                if current_step >= max_steps:
                    result["error"] = "Maximum application steps reached"
                    break
            
            # Final verification
            if not result["success"] and not result["error"]:
                # Check if we're back to the job page or see success message
                if await page.locator('text="Application sent", text="Your application was sent"').count() > 0:
                    result["success"] = True
                    result["steps"].append("Application confirmed via success message")
                else:
                    result["error"] = "Application status unclear"
                    
        except Exception as e:
            result["error"] = f"Error during Easy Apply process: {str(e)}"
            logger.error(f"❌ Easy Apply error: {e}")
        
        return result
    
    async def _generate_cover_letter(self, job_data: Dict[str, Any]) -> str:
        """Generate AI-powered cover letter for the job"""
        try:
            if self.linkedin_reader:
                prompt = f"""
                Write a professional cover letter for this job application:
                
                Job Title: {job_data.get('title', 'Software Engineer')}
                Company: {job_data.get('company', 'Company')}
                Location: {job_data.get('location', 'Remote')}
                
                Applicant Background:
                - ALX Software Engineering graduate
                - Python developer with experience in AI and cybersecurity
                - Passionate about technology and continuous learning
                - Strong problem-solving skills
                
                Requirements:
                - Keep it under 300 words
                - Professional but personable tone
                - Highlight relevant skills
                - Show enthusiasm for the role
                - Mention specific interest in the company's work
                - End with a call to action
                
                Format: Regular paragraph format without special formatting
                """
                
                cover_letter = await self.linkedin_reader.generate_content("cover_letter", prompt)
                
                if cover_letter:
                    return cover_letter
            
            # Fallback template
            cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_data.get('title', 'Software Engineer')} position at {job_data.get('company', 'your company')}. As an ALX Software Engineering graduate with a passion for technology and continuous learning, I am excited about the opportunity to contribute to your team.

My background includes experience with Python development, AI technologies, and cybersecurity fundamentals. I have developed strong problem-solving skills and enjoy tackling complex technical challenges. I am particularly drawn to {job_data.get('company', 'your company')} because of your innovative approach to technology.

I would welcome the opportunity to discuss how my skills and enthusiasm can contribute to your team's success. Thank you for considering my application.

Best regards,
[Your Name]"""
            
            return cover_letter
            
        except Exception as e:
            logger.error(f"❌ Error generating cover letter: {e}")
            return ""
    
    def _has_already_applied(self, job_id: str) -> bool:
        """Check if already applied to this job"""
        try:
            applied_ids = {app.get("job_id") for app in self.applications_data.get("applications", [])}
            return job_id in applied_ids
        except Exception:
            return False
    
    def _is_company_blacklisted(self, company: str) -> bool:
        """Check if company is blacklisted"""
        try:
            blacklisted = [c.lower() for c in self.applications_data.get("blacklisted_companies", [])]
            return company.lower() in blacklisted
        except Exception:
            return False
    
    def _has_reached_daily_limit(self) -> bool:
        """Check if daily application limit has been reached"""
        try:
            today_count = self._get_daily_application_count()
            return today_count >= self.max_daily_applications
        except Exception:
            return False
    
    def _get_daily_application_count(self) -> int:
        """Get number of applications submitted today"""
        try:
            today = datetime.now().date().isoformat()
            return self.applications_data.get("daily_counts", {}).get(today, 0)
        except Exception:
            return 0
    
    def _record_application(self, job_data: Dict[str, Any], result: Dict[str, Any]):
        """Record a job application"""
        try:
            application_record = {
                "timestamp": result["timestamp"],
                "job_id": result["job_id"],
                "job_title": result["job_title"],
                "company": result["company"],
                "job_url": job_data.get("url", ""),
                "location": job_data.get("location", ""),
                "application_method": result["application_method"],
                "success": result["success"],
                "cv_used": result["cv_used"],
                "cover_letter_generated": result["cover_letter_generated"],
                "cover_letter_content": result["cover_letter_content"],
                "application_steps": result["application_steps"],
                "error": result.get("error", ""),
                "relevant_score": job_data.get("relevant_score", 0)
            }
            
            self.applications_data["applications"].append(application_record)
            self.applications_data["total_applications"] += 1
            
            # Update success rate
            successful_apps = sum(1 for app in self.applications_data["applications"] if app["success"])
            total_apps = len(self.applications_data["applications"])
            self.applications_data["success_rate"] = successful_apps / total_apps if total_apps > 0 else 0
            
            self._save_applications_data()
        except Exception as e:
            logger.error(f"❌ Error recording application: {e}")
    
    def get_application_statistics(self) -> Dict[str, Any]:
        """Get application statistics"""
        try:
            applications = self.applications_data.get("applications", [])
            
            # Calculate statistics
            total_apps = len(applications)
            successful_apps = sum(1 for app in applications if app["success"])
            success_rate = successful_apps / total_apps if total_apps > 0 else 0
            
            # Recent applications (last 7 days)
            week_ago = datetime.now() - timedelta(days=7)
            recent_apps = [
                app for app in applications 
                if datetime.fromisoformat(app["timestamp"]) > week_ago
            ]
            
            return {
                "total_applications": total_apps,
                "successful_applications": successful_apps,
                "success_rate": success_rate,
                "recent_applications_7d": len(recent_apps),
                "applications_today": self._get_daily_application_count(),
                "daily_limit": self.max_daily_applications,
                "remaining_today": max(0, self.max_daily_applications - self._get_daily_application_count()),
                "blacklisted_companies": len(self.applications_data.get("blacklisted_companies", [])),
                "preferred_companies": len(self.applications_data.get("preferred_companies", []))
            }
        except Exception as e:
            logger.error(f"❌ Error getting application statistics: {e}")
            return {
                "total_applications": 0,
                "successful_applications": 0,
                "success_rate": 0,
                "recent_applications_7d": 0,
                "applications_today": 0,
                "daily_limit": self.max_daily_applications,
                "remaining_today": self.max_daily_applications,
                "blacklisted_companies": 0,
                "preferred_companies": 0
            }

# Example usage and testing
async def main():
    """Test the application manager"""
    try:
        manager = LinkedInApplicationManager()
        
        print("📝 Testing LinkedIn Application Manager")
        print("=" * 50)
        
        # Show current statistics
        stats = manager.get_application_statistics()
        print(f"📊 Application Statistics:")
        print(f"  Total Applications: {stats['total_applications']}")
        print(f"  Success Rate: {stats['success_rate']:.1%}")
        print(f"  Applications Today: {stats['applications_today']}/{stats['daily_limit']}")
        print(f"  Remaining Today: {stats['remaining_today']}")
        
        # Test with sample job data
        sample_job = {
            "id": "test_job_123",
            "title": "Python Developer",
            "company": "TechCorp",
            "location": "Remote",
            "url": "https://www.linkedin.com/jobs/view/123456789",
            "relevant_score": 8
        }
        
        print(f"\n🧪 Testing job application (DRY RUN)...")
        result = await manager.apply_to_job(sample_job, dry_run=True)
        
        print(f"📊 Application Result:")
        print(f"  Success: {result['success']}")
        print(f"  Job: {result['job_title']} at {result['company']}")
        print(f"  Cover Letter Generated: {result['cover_letter_generated']}")
        
        if result['cover_letter_content']:
            print(f"  Cover Letter Preview: {result['cover_letter_content'][:100]}...")
        
        if result['application_steps']:
            print(f"  Application Steps:")
            for step in result['application_steps']:
                print(f"    - {step}")
        
        if result.get('error'):
            print(f"  Error: {result['error']}")
        
        print("\n✅ Application manager test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
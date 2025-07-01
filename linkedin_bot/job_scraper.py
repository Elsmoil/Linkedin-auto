import asyncio
import logging
import json
import os
import re
from typing import Optional, Dict, Any, List
from pathlib import Path
from playwright.async_api import Page, BrowserContext
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote_plus

# Configure logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import our modules with better error handling
env_handler = None
LinkedInAuthenticator = None
LinkedInPerformanceTracker = None

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
    from analytics.performance_tracker import LinkedInPerformanceTracker
    logger.info("✅ Imported LinkedInPerformanceTracker")
except ImportError as e:
    logger.warning(f"⚠️ Could not import LinkedInPerformanceTracker: {e}")

class LinkedInJobScraper:
    """Advanced LinkedIn job scraping with AI-powered filtering and analysis"""
    
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
        
        # Optional components
        try:
            self.performance_tracker = LinkedInPerformanceTracker() if LinkedInPerformanceTracker else None
            if self.performance_tracker:
                logger.info("✅ Initialized LinkedInPerformanceTracker")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize LinkedInPerformanceTracker: {e}")
            self.performance_tracker = None
        
        self._load_config()
        self._initialize_job_tracking()
        
    def _load_config(self):
        """Load job scraper configuration"""
        try:
            if env_handler:
                linkedin_config = env_handler.get_config('linkedin')
                self.timeout = linkedin_config.get('timeout', 30000)
                
                # Job search configuration
                job_config = env_handler.get_config('job_search')
                self.search_keywords = job_config.get('keywords', 'software engineer').split(',')
                self.search_locations = job_config.get('locations', 'Remote').split(',')
                self.experience_levels = job_config.get('experience_levels', 'entry,associate').split(',')
                self.job_types = job_config.get('job_types', 'full-time').split(',')
                self.max_results_per_search = job_config.get('max_results_per_search', 50)
            else:
                # Fallback to environment variables
                self.timeout = int(os.getenv('LINKEDIN_TIMEOUT', '30000'))
                self.search_keywords = os.getenv('JOB_SEARCH_KEYWORDS', 'software engineer').split(',')
                self.search_locations = os.getenv('JOB_SEARCH_LOCATIONS', 'Remote').split(',')
                self.experience_levels = os.getenv('JOB_EXPERIENCE_LEVELS', 'entry,associate').split(',')
                self.job_types = os.getenv('JOB_TYPES', 'full-time').split(',')
                self.max_results_per_search = int(os.getenv('MAX_RESULTS_PER_SEARCH', '50'))
            
            # Clean up lists
            self.search_keywords = [k.strip() for k in self.search_keywords if k.strip()]
            self.search_locations = [l.strip() for l in self.search_locations if l.strip()]
            self.experience_levels = [e.strip() for e in self.experience_levels if e.strip()]
            self.job_types = [t.strip() for t in self.job_types if t.strip()]
            
            self.jobs_file = Path("logs/scraped_jobs.json")
            self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info("✅ Job scraper configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Error loading job scraper configuration: {e}")
            # Set default values
            self.timeout = 30000
            self.search_keywords = ['software engineer']
            self.search_locations = ['Remote']
            self.experience_levels = ['entry', 'associate']
            self.job_types = ['full-time']
            self.max_results_per_search = 50
        
    def _initialize_job_tracking(self):
        """Initialize job tracking"""
        try:
            self.scraped_jobs = self._load_scraped_jobs()
            logger.info("✅ Job tracking initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing job tracking: {e}")
            self.scraped_jobs = {
                "created_at": datetime.now().isoformat(),
                "total_jobs_found": 0,
                "jobs": [],
                "last_scrape": None,
                "search_history": []
            }
        
    def _load_scraped_jobs(self) -> Dict[str, Any]:
        """Load previously scraped jobs"""
        if self.jobs_file.exists():
            try:
                with open(self.jobs_file, 'r') as f:
                    data = json.load(f)
                logger.info("✅ Loaded scraped jobs history")
                return data
            except Exception as e:
                logger.warning(f"⚠️ Failed to load scraped jobs: {e}")
        
        return {
            "created_at": datetime.now().isoformat(),
            "total_jobs_found": 0,
            "jobs": [],
            "last_scrape": None,
            "search_history": []
        }
    
    def _save_scraped_jobs(self):
        """Save scraped jobs to file"""
        try:
            with open(self.jobs_file, 'w') as f:
                json.dump(self.scraped_jobs, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save scraped jobs: {e}")
    
    async def search_jobs(self, keywords: Optional[List[str]] = None, locations: Optional[List[str]] = None,
                         experience_levels: Optional[List[str]] = None, job_types: Optional[List[str]] = None,
                         posted_within_days: int = 7) -> Dict[str, Any]:
        """Search for jobs on LinkedIn with specified criteria"""
        
        # Use provided criteria or defaults
        search_keywords = keywords or self.search_keywords
        search_locations = locations or self.search_locations
        search_experience = experience_levels or self.experience_levels
        search_job_types = job_types or self.job_types
        
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "total_jobs_found": 0,
            "new_jobs": 0,
            "jobs": [],
            "search_criteria": {
                "keywords": search_keywords,
                "locations": search_locations,
                "experience_levels": search_experience,
                "job_types": search_job_types,
                "posted_within_days": posted_within_days
            },
            "errors": []
        }
        
        # Check if authenticator is available
        if not hasattr(self, 'authenticator') or not self.authenticator:
            result["errors"].append("LinkedIn authenticator not available")
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
                    result["errors"].append(f"Authentication failed: {auth_result['message']}")
                    return result
                
                all_jobs = []
                
                # Search for each keyword-location combination
                for keyword in search_keywords:
                    for location in search_locations:
                        try:
                            logger.info(f"🔍 Searching for '{keyword}' in '{location}'")
                            
                            jobs = await self._search_jobs_for_criteria(
                                page, keyword, location, search_experience, 
                                search_job_types, posted_within_days
                            )
                            
                            all_jobs.extend(jobs)
                            
                            # Add delay between searches
                            await asyncio.sleep(5)
                            
                        except Exception as e:
                            logger.error(f"❌ Error searching for {keyword} in {location}: {e}")
                            result["errors"].append(f"{keyword} in {location}: {str(e)}")
                
                # Remove duplicates and filter
                unique_jobs = self._remove_duplicate_jobs(all_jobs)
                filtered_jobs = await self._filter_relevant_jobs(unique_jobs)
                
                result.update({
                    "success": True,
                    "total_jobs_found": len(filtered_jobs),
                    "jobs": filtered_jobs
                })
                
                # Track new jobs
                new_jobs = self._identify_new_jobs(filtered_jobs)
                result["new_jobs"] = len(new_jobs)
                
                # Update scraped jobs history
                self._update_scraped_jobs_history(filtered_jobs, result["search_criteria"])
                
                # Track activity if performance tracker is available
                if self.performance_tracker:
                    try:
                        self.performance_tracker.track_activity(
                            "job_search", "success", {
                                "jobs_found": len(filtered_jobs),
                                "new_jobs": len(new_jobs),
                                "keywords": search_keywords
                            }
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ Could not track activity: {e}")
                
                logger.info(f"✅ Job search completed: {len(filtered_jobs)} jobs found, {len(new_jobs)} new")
                
        except Exception as e:
            logger.error(f"❌ Job search failed: {e}")
            result["errors"].append(str(e))
        finally:
            if browser:
                await browser.close()
        
        return result
    
    async def _search_jobs_for_criteria(self, page: Page, keyword: str, location: str,
                                      experience_levels: List[str], job_types: List[str],
                                      posted_within_days: int) -> List[Dict[str, Any]]:
        """Search jobs for specific criteria combination"""
        
        # Build LinkedIn jobs search URL
        base_url = "https://www.linkedin.com/jobs/search/?"
        
        params = {
            "keywords": keyword,
            "location": location,
            "f_TPR": f"r{posted_within_days * 86400}",  # Posted within days (in seconds)
            "sortBy": "DD"  # Sort by date
        }
        
        # Add job types and experience levels if specified
        if job_types:
            params["f_JT"] = ",".join(job_types)
        if experience_levels:
            params["f_E"] = ",".join(experience_levels)
        
        search_url = base_url + urlencode(params)
        
        # Navigate to search page
        await page.goto(search_url, timeout=self.timeout)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        jobs = []
        
        try:
            # Wait for job results to load
            await page.wait_for_selector('.jobs-search__results-list', timeout=10000)
            
            # Scroll to load more jobs
            await self._scroll_to_load_jobs(page)
            
            # Get all job cards
            job_cards = await page.locator('.base-card').all()
            
            logger.info(f"📄 Found {len(job_cards)} job cards for '{keyword}' in '{location}'")
            
            for i, card in enumerate(job_cards[:self.max_results_per_search]):
                try:
                    job_data = await self._extract_job_data_from_card(page, card, i)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    logger.debug(f"Error extracting job {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"❌ Error scraping jobs for {keyword} in {location}: {e}")
        
        return jobs
    
    async def _scroll_to_load_jobs(self, page: Page):
        """Scroll down to load more job results"""
        try:
            # Scroll down multiple times to load more jobs
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                # Check if "Show more jobs" button exists and click it
                show_more_button = page.locator('button:has-text("Show more jobs"), button:has-text("See more jobs")')
                if await show_more_button.count() > 0:
                    await show_more_button.first.click()
                    await asyncio.sleep(3)
        except Exception as e:
            logger.debug(f"Error scrolling to load jobs: {e}")
    
    async def _extract_job_data_from_card(self, page: Page, card, index: int) -> Optional[Dict[str, Any]]:
        """Extract job data from a job card"""
        try:
            # Get job link
            job_link = await card.locator('a[data-control-name="job_card_click"]').first.get_attribute('href')
            if not job_link:
                return None
            
            # Ensure full URL
            if job_link.startswith('/'):
                job_link = f"https://www.linkedin.com{job_link}"
            
            # Extract basic info from card
            title_element = card.locator('.base-search-card__title')
            company_element = card.locator('.base-search-card__subtitle')
            location_element = card.locator('.job-search-card__location')
            
            title = await title_element.text_content() if await title_element.count() > 0 else "Unknown"
            company = await company_element.text_content() if await company_element.count() > 0 else "Unknown"
            location = await location_element.text_content() if await location_element.count() > 0 else "Unknown"
            
            # Clean up text
            title = title.strip() if title else "Unknown"
            company = company.strip() if company else "Unknown"
            location = location.strip() if location else "Unknown"
            
            # Extract job ID from URL
            job_id_match = re.search(r'/jobs/view/(\d+)', job_link)
            job_id = job_id_match.group(1) if job_id_match else f"unknown_{index}"
            
            job_data = {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "url": job_link,
                "scraped_at": datetime.now().isoformat(),
                "applied": False,
                "relevant_score": 0,
                "description": "",
                "requirements": [],
                "salary_info": "",
                "job_type": "",
                "experience_level": "",
                "posted_date": ""
            }
            
            return job_data
            
        except Exception as e:
            logger.debug(f"Error extracting job data from card {index}: {e}")
            return None
    
    async def get_detailed_job_info(self, job_url: str) -> Dict[str, Any]:
        """Get detailed information for a specific job"""
        result = {
            "success": False,
            "job_data": {},
            "error": ""
        }
        
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
                
                # Navigate to job page
                await page.goto(job_url, timeout=self.timeout)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(3)
                
                # Extract detailed job information
                job_data = await self._extract_detailed_job_data(page)
                
                result.update({
                    "success": True,
                    "job_data": job_data
                })
                
        except Exception as e:
            logger.error(f"❌ Error getting detailed job info: {e}")
            result["error"] = str(e)
        finally:
            if browser:
                await browser.close()
        
        return result
    
    async def _extract_detailed_job_data(self, page: Page) -> Dict[str, Any]:
        """Extract detailed job data from job page"""
        try:
            # Wait for job description to load
            await page.wait_for_selector('.show-more-less-html__markup', timeout=10000)
            
            # Extract job description
            description_element = page.locator('.show-more-less-html__markup')
            description = await description_element.text_content() if await description_element.count() > 0 else ""
            
            # Extract job criteria
            criteria_elements = await page.locator('.description__job-criteria-list li').all()
            criteria = {}
            
            for element in criteria_elements:
                try:
                    label_elem = element.locator('.description__job-criteria-subheader')
                    value_elem = element.locator('.description__job-criteria-text')
                    
                    if await label_elem.count() > 0 and await value_elem.count() > 0:
                        label = await label_elem.text_content()
                        value = await value_elem.text_content()
                        if label and value:
                            criteria[label.strip().lower().replace(' ', '_')] = value.strip()
                except:
                    continue
            
            # Extract salary information (if available)
            salary_element = page.locator('[class*="salary"], [class*="compensation"]')
            salary_info = await salary_element.text_content() if await salary_element.count() > 0 else ""
            
            # Extract requirements from description
            requirements = self._extract_requirements_from_description(description) if description else []
            
            return {
                "description": description,
                "criteria": criteria,
                "salary_info": salary_info,
                "requirements": requirements,
                "job_type": criteria.get("employment_type", ""),
                "experience_level": criteria.get("seniority_level", ""),
                "industry": criteria.get("industries", "")
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting detailed job data: {e}")
            return {}
    
    def _extract_requirements_from_description(self, description: str) -> List[str]:
        """Extract key requirements from job description using pattern matching"""
        if not description:
            return []
        
        requirements = []
        
        # Common requirement patterns
        patterns = [
            r'(?i)(?:require[sd]?|must have|need|essential).*?(?:experience with|knowledge of|proficiency in)\s*([^.]*)',
            r'(?i)(\d+\+?\s*years?\s*(?:of\s*)?experience)',
            r'(?i)(bachelor\'?s?|master\'?s?|degree)\s*(?:in\s*)?([^.]*)',
            r'(?i)(?:proficient|experienced|skilled)\s*(?:in|with)\s*([^.]*)',
            r'(?i)(?:knowledge|understanding)\s*(?:of|in)\s*([^.]*)'
        ]
        
        for pattern in patterns:
            try:
                matches = re.findall(pattern, description)
                for match in matches:
                    if isinstance(match, tuple):
                        req = ' '.join(match).strip()
                    else:
                        req = match.strip()
                    
                    if req and len(req) > 3 and len(req) < 100:
                        requirements.append(req)
            except Exception as e:
                logger.debug(f"Error in pattern matching: {e}")
                continue
        
        # Remove duplicates and limit
        return list(set(requirements))[:10]
    
    def _remove_duplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs based on company and title"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            # Create a unique identifier
            identifier = f"{job.get('company', '').lower()}_{job.get('title', '').lower()}"
            
            if identifier not in seen:
                seen.add(identifier)
                unique_jobs.append(job)
        
        logger.info(f"🔄 Removed {len(jobs) - len(unique_jobs)} duplicate jobs")
        return unique_jobs
    
    async def _filter_relevant_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter jobs based on relevance to user's profile"""
        relevant_jobs = []
        
        # Keywords that indicate relevant jobs for software engineering
        relevant_keywords = [
            'software', 'developer', 'engineer', 'programming', 'python',
            'backend', 'frontend', 'full-stack', 'api', 'database',
            'ai', 'artificial intelligence', 'machine learning', 'data',
            'cybersecurity', 'security', 'devops', 'cloud', 'aws'
        ]
        
        # Keywords to avoid
        avoid_keywords = [
            'sales', 'marketing', 'manager', 'director', 'vp',
            'senior manager', 'account', 'business development'
        ]
        
        for job in jobs:
            title = job.get('title', '').lower()
            company = job.get('company', '').lower()
            
            # Calculate relevance score
            relevance_score = 0
            
            # Check for relevant keywords
            for keyword in relevant_keywords:
                if keyword in title:
                    relevance_score += 2
                if keyword in company:
                    relevance_score += 1
            
            # Penalize for avoid keywords
            for keyword in avoid_keywords:
                if keyword in title:
                    relevance_score -= 3
            
            # Only include jobs with positive relevance score
            if relevance_score > 0:
                job['relevant_score'] = relevance_score
                relevant_jobs.append(job)
        
        # Sort by relevance score
        relevant_jobs.sort(key=lambda x: x['relevant_score'], reverse=True)
        
        logger.info(f"✅ Filtered to {len(relevant_jobs)} relevant jobs")
        return relevant_jobs
    
    def _identify_new_jobs(self, current_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify jobs that haven't been seen before"""
        try:
            existing_job_ids = {job.get('id') for job in self.scraped_jobs.get('jobs', [])}
            new_jobs = [job for job in current_jobs if job.get('id') not in existing_job_ids]
            return new_jobs
        except Exception as e:
            logger.error(f"❌ Error identifying new jobs: {e}")
            return current_jobs  # Return all jobs if error
    
    def _update_scraped_jobs_history(self, jobs: List[Dict[str, Any]], search_criteria: Dict[str, Any]):
        """Update the scraped jobs history"""
        try:
            # Add new jobs to history
            existing_ids = {job.get('id') for job in self.scraped_jobs.get('jobs', [])}
            new_jobs = [job for job in jobs if job.get('id') not in existing_ids]
            
            self.scraped_jobs['jobs'].extend(new_jobs)
            self.scraped_jobs['total_jobs_found'] = len(self.scraped_jobs['jobs'])
            self.scraped_jobs['last_scrape'] = datetime.now().isoformat()
            
            # Add search to history
            search_entry = {
                "timestamp": datetime.now().isoformat(),
                "criteria": search_criteria,
                "jobs_found": len(jobs),
                "new_jobs": len(new_jobs)
            }
            
            if 'search_history' not in self.scraped_jobs:
                self.scraped_jobs['search_history'] = []
            
            self.scraped_jobs['search_history'].append(search_entry)
            
            # Keep only last 50 searches
            if len(self.scraped_jobs['search_history']) > 50:
                self.scraped_jobs['search_history'] = self.scraped_jobs['search_history'][-50:]
            
            # Save to file
            self._save_scraped_jobs()
            
        except Exception as e:
            logger.error(f"❌ Error updating scraped jobs history: {e}")
    
    def get_job_statistics(self) -> Dict[str, Any]:
        """Get job scraping statistics"""
        try:
            return {
                "total_jobs_scraped": self.scraped_jobs.get('total_jobs_found', 0),
                "last_scrape": self.scraped_jobs.get('last_scrape'),
                "recent_searches": len(self.scraped_jobs.get('search_history', [])),
                "jobs_by_relevance": self._get_jobs_by_relevance_stats()
            }
        except Exception as e:
            logger.error(f"❌ Error getting job statistics: {e}")
            return {
                "total_jobs_scraped": 0,
                "last_scrape": None,
                "recent_searches": 0,
                "jobs_by_relevance": {"high": 0, "medium": 0, "low": 0}
            }
    
    def _get_jobs_by_relevance_stats(self) -> Dict[str, int]:
        """Get statistics of jobs by relevance score"""
        try:
            jobs = self.scraped_jobs.get('jobs', [])
            stats = {"high": 0, "medium": 0, "low": 0}
            
            for job in jobs:
                score = job.get('relevant_score', 0)
                if score >= 5:
                    stats["high"] += 1
                elif score >= 2:
                    stats["medium"] += 1
                else:
                    stats["low"] += 1
            
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting relevance stats: {e}")
            return {"high": 0, "medium": 0, "low": 0}

# Convenience functions
async def search_jobs_simple(keywords: List[str], locations: Optional[List[str]] = None):
    """Simple function to search for jobs"""
    try:
        scraper = LinkedInJobScraper()
        return await scraper.search_jobs(keywords, locations if locations is not None else [])
    except Exception as e:
        logger.error(f"❌ Error in search_jobs_simple: {e}")
        return {"success": False, "error": str(e), "jobs": []}

async def get_job_details_simple(job_url: str):
    """Simple function to get job details"""
    try:
        scraper = LinkedInJobScraper()
        return await scraper.get_detailed_job_info(job_url)
    except Exception as e:
        logger.error(f"❌ Error in get_job_details_simple: {e}")
        return {"success": False, "error": str(e), "job_data": {}}

# Example usage and testing
async def main():
    """Test the job scraper"""
    try:
        scraper = LinkedInJobScraper()
        
        print("🔍 Testing LinkedIn Job Scraper")
        print("=" * 50)
        
        # Show current statistics
        stats = scraper.get_job_statistics()
        print(f"📊 Job Statistics:")
        print(f"  Total Jobs Scraped: {stats['total_jobs_scraped']}")
        print(f"  Last Scrape: {stats['last_scrape']}")
        print(f"  High Relevance: {stats['jobs_by_relevance']['high']}")
        
        # Test job search
        print(f"\n🧪 Testing job search...")
        result = await scraper.search_jobs(
            keywords=["python developer", "software engineer"],
            locations=["Remote", "United States"]
        )
        
        print(f"\n📊 Search Result:")
        print(f"  Success: {result['success']}")
        print(f"  Total Jobs Found: {result['total_jobs_found']}")
        print(f"  New Jobs: {result['new_jobs']}")
        
        if result['jobs']:
            print(f"\n📋 Sample Jobs:")
            for i, job in enumerate(result['jobs'][:3]):
                print(f"  {i+1}. {job['title']} at {job['company']}")
                print(f"     Location: {job['location']}")
                print(f"     Relevance: {job['relevant_score']}")
        
        if result['errors']:
            print(f"\n❌ Errors:")
            for error in result['errors']:
                print(f"  - {error}")
        
        print("\n✅ Job scraper test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
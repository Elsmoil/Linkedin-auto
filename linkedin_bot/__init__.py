"""
LinkedIn Automation Bot Package

A comprehensive LinkedIn automation system with AI-powered content generation,
intelligent engagement, profile optimization, and job application automation.

Author: ALX Software Engineering Graduate
Version: 1.0.0
"""

import logging
from pathlib import Path

# Import main classes with error handling
try:
    from .authenticator import LinkedInAuthenticator
except ImportError as e:
    print(f"⚠️ Warning: Could not import LinkedInAuthenticator: {e}")
    LinkedInAuthenticator = None

try:
    from .profile_updater import LinkedInProfileUpdater
except ImportError as e:
    print(f"⚠️ Warning: Could not import LinkedInProfileUpdater: {e}")
    LinkedInProfileUpdater = None

try:
    from .engagement_manager import LinkedInEngagementManager
except ImportError as e:
    print(f"⚠️ Warning: Could not import LinkedInEngagementManager: {e}")
    LinkedInEngagementManager = None

# Import new classes with error handling
try:
    from .job_scraper import LinkedInJobScraper
except ImportError as e:
    print(f"⚠️ Warning: Could not import LinkedInJobScraper: {e}")
    LinkedInJobScraper = None

try:
    from .application_manager import LinkedInApplicationManager
except ImportError as e:
    print(f"⚠️ Warning: Could not import LinkedInApplicationManager: {e}")
    LinkedInApplicationManager = None

# Package metadata
__version__ = "1.0.0"
__author__ = "ALX Graduate"
__description__ = "AI-Powered LinkedIn Automation System"

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Configure package logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'linkedin_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Export available classes only
__all__ = []

if LinkedInAuthenticator:
    __all__.append("LinkedInAuthenticator")
if LinkedInProfileUpdater:
    __all__.append("LinkedInProfileUpdater")
if LinkedInEngagementManager:
    __all__.append("LinkedInEngagementManager")
if LinkedInJobScraper:
    __all__.append("LinkedInJobScraper")
if LinkedInApplicationManager:
    __all__.append("LinkedInApplicationManager")

# Add version info
__all__.extend(["__version__", "__author__", "__description__"])

# Package initialization
logger.info(f"🚀 LinkedIn Bot Package v{__version__} initialized")

# Convenience functions for quick access
def create_authenticator():
    """Create and return a LinkedInAuthenticator instance"""
    if LinkedInAuthenticator:
        return LinkedInAuthenticator()
    else:
        raise ImportError("LinkedInAuthenticator not available")

def create_engagement_manager():
    """Create and return a LinkedInEngagementManager instance"""
    if LinkedInEngagementManager:
        return LinkedInEngagementManager()
    else:
        raise ImportError("LinkedInEngagementManager not available")

def create_profile_updater():
    """Create and return a LinkedInProfileUpdater instance"""
    if LinkedInProfileUpdater:
        return LinkedInProfileUpdater()
    else:
        raise ImportError("LinkedInProfileUpdater not available")

def create_job_scraper():
    """Create and return a LinkedInJobScraper instance"""
    if LinkedInJobScraper:
        return LinkedInJobScraper()
    else:
        raise ImportError("LinkedInJobScraper not available")

def create_application_manager():
    """Create and return a LinkedInApplicationManager instance"""
    if LinkedInApplicationManager:
        return LinkedInApplicationManager()
    else:
        raise ImportError("LinkedInApplicationManager not available")

# Health check function
def health_check():
    """Perform a basic health check of the package"""
    try:
        # Check if required directories exist
        required_dirs = ["logs", "config", "analytics"]
        missing_dirs = []
        
        for dir_name in required_dirs:
            if not Path(dir_name).exists():
                missing_dirs.append(dir_name)
                logger.warning(f"⚠️ Directory '{dir_name}' not found")
        
        # Check if main modules are available
        available_modules = []
        if LinkedInAuthenticator:
            available_modules.append("authenticator")
        if LinkedInProfileUpdater:
            available_modules.append("profile_updater")
        if LinkedInEngagementManager:
            available_modules.append("engagement_manager")
        if LinkedInJobScraper:
            available_modules.append("job_scraper")
        if LinkedInApplicationManager:
            available_modules.append("application_manager")
        
        logger.info(f"✅ Available modules: {', '.join(available_modules)}")
        
        if missing_dirs:
            logger.warning(f"⚠️ Missing directories: {', '.join(missing_dirs)}")
        else:
            logger.info("✅ All required directories found")
        
        return len(available_modules) > 0
        
    except Exception as e:
        logger.error(f"❌ LinkedIn Bot package health check failed: {e}")
        return False

# Auto-run health check on import (only if not main)
if __name__ != "__main__":
    health_check()
# content_generator.py
import asyncio
import logging
import json
import random
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta

# Import our modules
try:
    from config.env_handler import env_handler
    from ai_modules.linkedin_reader import LinkedInReader
    from model_switcher import get_model_for_task
except ImportError:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    env_handler = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInContentGenerator:
    """Advanced AI-powered LinkedIn content generator with multiple content types"""
    
    def __init__(self):
        self.linkedin_reader = LinkedInReader()
        self._load_config()
        self._initialize_content_tracking()
        
    def _load_config(self):
        """Load content generator configuration"""
        if env_handler:
            linkedin_config = env_handler.get_config('linkedin')
            self.user_name = linkedin_config.get('user_name', 'Professional')
            self.industry = linkedin_config.get('industry', 'Software Engineering')
        else:
            self.user_name = os.getenv('LINKEDIN_USER_NAME', 'Professional')
            self.industry = os.getenv('LINKEDIN_INDUSTRY', 'Software Engineering')
        
        self.content_history_file = Path("logs/content_history.json")
        self.content_history_file.parent.mkdir(exist_ok=True)
        
        # Content themes based on your profile
        self.content_themes = {
            'technical': [
                'Python programming tips',
                'Software engineering best practices',
                'AI and machine learning insights',
                'Cybersecurity fundamentals',
                'Linux system administration',
                'Network security concepts',
                'Penetration testing methodologies',
                'Clean code principles',
                'Database optimization',
                'API design patterns'
            ],
            'career': [
                'ALX Software Engineering journey',
                'Career growth in tech',
                'Learning programming languages',
                'Building tech skills',
                'Remote work in software development',
                'Tech interview preparation',
                'Open source contributions',
                'Networking in tech industry',
                'Continuous learning mindset',
                'Tech community involvement'
            ],
            'industry': [
                'Future of software development',
                'AI impact on cybersecurity',
                'Emerging tech trends',
                'Digital transformation',
                'Tech startup ecosystem',
                'Innovation in technology',
                'Cloud computing evolution',
                'Mobile development trends',
                'IoT security challenges',
                'Blockchain applications'
            ],
            'personal': [
                'Learning journey reflections',
                'Problem-solving approaches',
                'Work-life balance in tech',
                'Mentorship experiences',
                'Tech book recommendations',
                'Conference insights',
                'Project lessons learned',
                'Skill development strategies',
                'Team collaboration tips',
                'Professional growth stories'
            ]
        }
        
    def _initialize_content_tracking(self):
        """Initialize content generation tracking"""
        self.content_history = self._load_content_history()
        
    def _load_content_history(self) -> Dict[str, Any]:
        """Load existing content history"""
        if self.content_history_file.exists():
            try:
                with open(self.content_history_file, 'r') as f:
                    data = json.load(f)
                logger.info("✅ Loaded content generation history")
                return data
            except Exception as e:
                logger.warning(f"⚠️ Failed to load content history: {e}")
        
        return {
            "created_at": datetime.now().isoformat(),
            "total_content": 0,
            "content_by_type": {
                "posts": 0,
                "comments": 0,
                "messages": 0,
                "headlines": 0,
                "summaries": 0
            },
            "recent_content": [],
            "themes_used": {},
            "success_rate": 1.0
        }
    
    def _save_content_history(self):
        """Save content history to file"""
        try:
            with open(self.content_history_file, 'w') as f:
                json.dump(self.content_history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to save content history: {e}")
    
    async def generate_linkedin_post(self, theme: str = None, style: str = "professional") -> Dict[str, Any]:
        """Generate a LinkedIn post with specified theme and style"""
        result = {
            "success": False,
            "content_type": "post",
            "content": "",
            "theme": theme,
            "style": style,
            "timestamp": datetime.now().isoformat(),
            "word_count": 0,
            "hashtags": [],
            "model_used": ""
        }
        
        try:
            # Select theme if not provided
            if not theme:
                theme = self._select_optimal_theme()
            
            # Get specific topic for the theme
            topic = self._get_topic_for_theme(theme)
            
            # Generate post content
            logger.info(f"✍️ Generating LinkedIn post - Theme: {theme}, Topic: {topic}")
            
            post_content = await self._generate_post_content(topic, theme, style)
            if not post_content:
                result["error"] = "Failed to generate post content"
                return result
            
            # Extract hashtags
            hashtags = self._extract_hashtags(post_content)
            
            # Clean and format content
            formatted_content = self._format_post_content(post_content)
            
            result.update({
                "success": True,
                "content": formatted_content,
                "word_count": len(formatted_content.split()),
                "hashtags": hashtags,
                "model_used": get_model_for_task("writing"),
                "topic": topic
            })
            
            # Record content generation
            self._record_content_generation(result)
            
            logger.info(f"✅ LinkedIn post generated successfully ({result['word_count']} words)")
            
        except Exception as e:
            logger.error(f"❌ Error generating LinkedIn post: {e}")
            result["error"] = str(e)
        
        return result
    
    async def generate_professional_comment(self, post_context: str) -> Dict[str, Any]:
        """Generate a professional comment for a LinkedIn post"""
        result = {
            "success": False,
            "content_type": "comment",
            "content": "",
            "post_context": post_context[:100] + "...",
            "timestamp": datetime.now().isoformat(),
            "model_used": ""
        }
        
        try:
            logger.info("💬 Generating professional comment...")
            
            comment = await self._generate_comment_content(post_context)
            if not comment:
                result["error"] = "Failed to generate comment"
                return result
            
            result.update({
                "success": True,
                "content": comment,
                "model_used": get_model_for_task("writing")
            })
            
            # Record content generation
            self._record_content_generation(result)
            
            logger.info(f"✅ Professional comment generated: {comment[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Error generating comment: {e}")
            result["error"] = str(e)
        
        return result
    
    async def generate_connection_message(self, target_profile: str = "") -> Dict[str, Any]:
        """Generate a personalized connection message"""
        result = {
            "success": False,
            "content_type": "message",
            "content": "",
            "target_profile": target_profile,
            "timestamp": datetime.now().isoformat(),
            "model_used": ""
        }
        
        try:
            logger.info("📨 Generating connection message...")
            
            message = await self._generate_message_content(target_profile)
            if not message:
                result["error"] = "Failed to generate message"
                return result
            
            result.update({
                "success": True,
                "content": message,
                "model_used": get_model_for_task("writing")
            })
            
            # Record content generation
            self._record_content_generation(result)
            
            logger.info(f"✅ Connection message generated: {message[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Error generating message: {e}")
            result["error"] = str(e)
        
        return result
    
    async def generate_profile_headline(self) -> Dict[str, Any]:
        """Generate an optimized LinkedIn headline"""
        result = {
            "success": False,
            "content_type": "headline",
            "content": "",
            "timestamp": datetime.now().isoformat(),
            "character_count": 0,
            "model_used": ""
        }
        
        try:
            logger.info("📋 Generating LinkedIn headline...")
            
            headline = await self._generate_headline_content()
            if not headline:
                result["error"] = "Failed to generate headline"
                return result
            
            result.update({
                "success": True,
                "content": headline,
                "character_count": len(headline),
                "model_used": get_model_for_task("writing")
            })
            
            # Record content generation
            self._record_content_generation(result)
            
            logger.info(f"✅ LinkedIn headline generated: {headline}")
            
        except Exception as e:
            logger.error(f"❌ Error generating headline: {e}")
            result["error"] = str(e)
        
        return result
    
    async def generate_about_summary(self) -> Dict[str, Any]:
        """Generate an optimized About/Summary section"""
        result = {
            "success": False,
            "content_type": "summary",
            "content": "",
            "timestamp": datetime.now().isoformat(),
            "character_count": 0,
            "model_used": ""
        }
        
        try:
            logger.info("📄 Generating LinkedIn summary...")
            
            summary = await self._generate_summary_content()
            if not summary:
                result["error"] = "Failed to generate summary"
                return result
            
            result.update({
                "success": True,
                "content": summary,
                "character_count": len(summary),
                "model_used": get_model_for_task("writing")
            })
            
            # Record content generation
            self._record_content_generation(result)
            
            logger.info(f"✅ LinkedIn summary generated ({result['character_count']} characters)")
            
        except Exception as e:
            logger.error(f"❌ Error generating summary: {e}")
            result["error"] = str(e)
        
        return result
    
    def _select_optimal_theme(self) -> str:
        """Select the optimal theme based on usage history"""
        # Get theme usage from history
        themes_used = self.content_history.get("themes_used", {})
        
        # Find least used theme category
        theme_categories = list(self.content_themes.keys())
        least_used_category = min(theme_categories, key=lambda x: themes_used.get(x, 0))
        
        return least_used_category
    
    def _get_topic_for_theme(self, theme: str) -> str:
        """Get a specific topic for the given theme"""
        if theme in self.content_themes:
            return random.choice(self.content_themes[theme])
        return "Professional insights and experiences"
    
    async def _generate_post_content(self, topic: str, theme: str, style: str) -> Optional[str]:
        """Generate LinkedIn post content using AI"""
        try:
            context = f"""
            Create a LinkedIn post about: {topic}
            
            Requirements:
            - Theme: {theme}
            - Style: {style}
            - Length: 150-300 words
            - Include relevant hashtags (3-5)
            - Professional tone appropriate for software engineering/cybersecurity
            - Engaging and thought-provoking
            - Include a call-to-action or question
            - Personal insights welcome
            - Avoid excessive self-promotion
            
            Author background: ALX Software Engineering graduate with interests in AI and cybersecurity
            
            Format: Regular LinkedIn post with natural hashtag integration
            """
            
            # Use the writing model for content generation
            model = get_model_for_task("writing")
            logger.debug(f"Using model: {model} for post generation")
            
            content = await self.linkedin_reader.generate_content("post", context)
            return content
            
        except Exception as e:
            logger.error(f"❌ Error generating post content: {e}")
            return None
    
    async def _generate_comment_content(self, post_context: str) -> Optional[str]:
        """Generate comment content using AI"""
        try:
            context = f"""
            Write a professional LinkedIn comment responding to this post:
            
            "{post_context}"
            
            Requirements:
            - 1-2 sentences maximum
            - Professional and thoughtful
            - Add value to the conversation
            - No self-promotion
            - Genuine and engaging
            - Related to software engineering, AI, or cybersecurity if applicable
            - Encourage further discussion
            
            Tone: Professional but friendly, as a software engineer with AI/cybersecurity interests
            """
            
            content = await self.linkedin_reader.generate_content("comment", context)
            return content
            
        except Exception as e:
            logger.error(f"❌ Error generating comment content: {e}")
            return None
    
    async def _generate_message_content(self, target_profile: str) -> Optional[str]:
        """Generate connection message content using AI"""
        try:
            context = f"""
            Write a professional LinkedIn connection request message.
            
            Target profile context: {target_profile if target_profile else "Software engineering professional"}
            
            Requirements:
            - 2-3 sentences maximum
            - Mention shared interests in software engineering, AI, or cybersecurity
            - Professional and genuine
            - No excessive flattery
            - Clear reason for connecting
            - Personal but not overly familiar
            
            Your background: ALX Software Engineering graduate, interested in AI and cybersecurity
            """
            
            content = await self.linkedin_reader.generate_content("message", context)
            return content
            
        except Exception as e:
            logger.error(f"❌ Error generating message content: {e}")
            return None
    
    async def _generate_headline_content(self) -> Optional[str]:
        """Generate LinkedIn headline using AI"""
        try:
            context = f"""
            Create a professional LinkedIn headline for a software engineer.
            
            Background:
            - ALX Software Engineering graduate
            - Interests in AI and cybersecurity
            - Python developer
            - Looking to showcase technical skills and growth mindset
            
            Requirements:
            - Maximum 120 characters
            - Professional and compelling
            - Include key skills/technologies
            - Show career level and aspirations
            - Stand out to recruiters and peers
            - No excessive punctuation or emojis
            
            Examples style: "Software Engineer | Python Developer | AI & Cybersecurity Enthusiast | ALX Graduate"
            """
            
            content = await self.linkedin_reader.generate_content("headline", context)
            return content
            
        except Exception as e:
            logger.error(f"❌ Error generating headline content: {e}")
            return None
    
    async def _generate_summary_content(self) -> Optional[str]:
        """Generate LinkedIn summary/about section using AI"""
        try:
            context = f"""
            Write a professional LinkedIn About/Summary section for a software engineer.
            
            Background:
            - ALX Software Engineering graduate
            - Strong interests in AI and cybersecurity
            - Python developer with growing experience
            - Passionate about technology and continuous learning
            - Looking to connect with tech professionals and opportunities
            
            Requirements:
            - 200-400 words
            - Professional yet personable tone
            - Highlight technical skills and learning journey
            - Show passion for technology
            - Include call-to-action for networking
            - Structured with clear paragraphs
            - Showcase problem-solving mindset
            - Mention specific technologies and interests
            
            Structure suggestion:
            1. Brief introduction and current focus
            2. Technical skills and interests
            3. Learning journey and growth mindset
            4. Goals and networking call-to-action
            """
            
            content = await self.linkedin_reader.generate_content("summary", context)
            return content
            
        except Exception as e:
            logger.error(f"❌ Error generating summary content: {e}")
            return None
    
    def _extract_hashtags(self, content: str) -> List[str]:
        """Extract hashtags from content"""
        import re
        hashtags = re.findall(r'#\w+', content)
        return [tag.lower() for tag in hashtags]
    
    def _format_post_content(self, content: str) -> str:
        """Format and clean post content"""
        # Remove excessive line breaks
        content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())
        
        # Ensure proper spacing around hashtags
        content = content.replace('#', ' #').replace('  #', ' #')
        
        # Clean up extra spaces
        content = ' '.join(content.split())
        
        return content.strip()
    
    def _record_content_generation(self, result: Dict[str, Any]):
        """Record content generation in history"""
        try:
            content_type = result["content_type"]
            
            # Update counters
            self.content_history["total_content"] += 1
            self.content_history["content_by_type"][content_type + "s"] += 1
            
            # Update theme usage
            if "theme" in result:
                theme = result["theme"]
                if theme:
                    self.content_history["themes_used"][theme] = self.content_history["themes_used"].get(theme, 0) + 1
            
            # Add to recent content
            content_summary = {
                "timestamp": result["timestamp"],
                "type": content_type,
                "success": result["success"],
                "theme": result.get("theme"),
                "word_count": result.get("word_count", 0),
                "model_used": result.get("model_used", "unknown")
            }
            
            self.content_history["recent_content"].append(content_summary)
            
            # Keep only last 50 content generations
            if len(self.content_history["recent_content"]) > 50:
                self.content_history["recent_content"] = self.content_history["recent_content"][-50:]
            
            # Update success rate
            recent_successful = sum(1 for c in self.content_history["recent_content"][-20:] if c["success"])
            self.content_history["success_rate"] = recent_successful / min(20, len(self.content_history["recent_content"]))
            
            self._save_content_history()
            
        except Exception as e:
            logger.error(f"❌ Error recording content generation: {e}")
    
    def get_content_statistics(self) -> Dict[str, Any]:
        """Get content generation statistics"""
        recent_content = [c for c in self.content_history["recent_content"] 
                         if datetime.fromisoformat(c["timestamp"]) > datetime.now() - timedelta(days=7)]
        
        return {
            "total_content": self.content_history["total_content"],
            "content_by_type": self.content_history["content_by_type"],
            "themes_used": self.content_history["themes_used"],
            "success_rate": self.content_history["success_rate"],
            "recent_content_7d": len(recent_content),
            "recent_content": self.content_history["recent_content"][-10:]
        }
    
    async def generate_content_batch(self, count: int = 5) -> Dict[str, Any]:
        """Generate a batch of different content types"""
        result = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "generated_content": [],
            "errors": []
        }
        
        try:
            logger.info(f"📝 Generating batch of {count} content pieces...")
            
            # Generate different types of content
            content_types = ["post", "comment", "message", "headline"]
            
            for i in range(count):
                content_type = content_types[i % len(content_types)]
                
                try:
                    if content_type == "post":
                        content_result = await self.generate_linkedin_post()
                    elif content_type == "comment":
                        content_result = await self.generate_professional_comment("Sample tech post about software development")
                    elif content_type == "message":
                        content_result = await self.generate_connection_message("Software Engineer at Tech Company")
                    elif content_type == "headline":
                        content_result = await self.generate_profile_headline()
                    
                    if content_result["success"]:
                        result["generated_content"].append(content_result)
                    else:
                        result["errors"].append(f"{content_type}: {content_result.get('error', 'Unknown error')}")
                    
                    # Small delay between generations
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    result["errors"].append(f"{content_type}: {str(e)}")
            
            result["success"] = len(result["generated_content"]) > 0
            
            logger.info(f"✅ Batch generation completed - {len(result['generated_content'])}/{count} successful")
            
        except Exception as e:
            logger.error(f"❌ Batch generation failed: {e}")
            result["errors"].append(str(e))
        
        return result

# Convenience functions
async def generate_quick_post(theme: str = None):
    """Quick function to generate a LinkedIn post"""
    generator = LinkedInContentGenerator()
    return await generator.generate_linkedin_post(theme)

async def generate_quick_comment(post_context: str):
    """Quick function to generate a comment"""
    generator = LinkedInContentGenerator()
    return await generator.generate_professional_comment(post_context)

# Example usage and testing
async def main():
    """Test the content generator"""
    try:
        generator = LinkedInContentGenerator()
        
        print("✍️ Testing LinkedIn Content Generator")
        print("=" * 50)
        
        # Show current statistics
        stats = generator.get_content_statistics()
        print(f"📊 Content Statistics:")
        print(f"  Total Content: {stats['total_content']}")
        print(f"  Success Rate: {stats['success_rate']:.1%}")
        print(f"  Posts: {stats['content_by_type']['posts']}")
        print(f"  Comments: {stats['content_by_type']['comments']}")
        
        # Test different content types
        print(f"\n🧪 Testing different content types...")
        
        # Generate a LinkedIn post
        print(f"\n📝 Generating LinkedIn post...")
        post_result = await generator.generate_linkedin_post(theme="technical")
        if post_result["success"]:
            print(f"✅ Post generated ({post_result['word_count']} words)")
            print(f"Content preview: {post_result['content'][:100]}...")
            print(f"Hashtags: {', '.join(post_result['hashtags'])}")
        else:
            print(f"❌ Post generation failed: {post_result.get('error')}")
        
        # Generate a comment
        print(f"\n💬 Generating comment...")
        comment_result = await generator.generate_professional_comment("Great insights on Python programming and best practices!")
        if comment_result["success"]:
            print(f"✅ Comment generated: {comment_result['content']}")
        else:
            print(f"❌ Comment generation failed: {comment_result.get('error')}")
        
        # Generate a headline
        print(f"\n📋 Generating headline...")
        headline_result = await generator.generate_profile_headline()
        if headline_result["success"]:
            print(f"✅ Headline generated: {headline_result['content']}")
            print(f"Characters: {headline_result['character_count']}/120")
        else:
            print(f"❌ Headline generation failed: {headline_result.get('error')}")
        
        print("\n✅ Content generator test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
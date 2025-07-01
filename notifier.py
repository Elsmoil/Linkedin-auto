# notifier.py
import smtplib
import aiohttp
import asyncio
import logging
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

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

class NotificationManager:
    """Advanced notification manager supporting multiple channels"""
    
    def __init__(self):
        self._load_config()
        self._validate_config()
        
    def _load_config(self):
        """Load notification configuration"""
        if env_handler:
            self.email_config = env_handler.get_notification_config('email')
            self.discord_config = env_handler.get_notification_config('discord')
            self.slack_config = env_handler.get_notification_config('slack')
        else:
            # Fallback to environment variables
            self.email_config = {
                'enabled': os.getenv("NOTIFY_EMAIL_ENABLED", "true").lower() == "true",
                'from': os.getenv("NOTIFY_EMAIL_FROM"),
                'to': os.getenv("NOTIFY_EMAIL_TO"),
                'password': os.getenv("NOTIFY_EMAIL_PASSWORD") or os.getenv("EMAIL_APP_PASSWORD"),
                'smtp_server': os.getenv("SMTP_SERVER", "smtp.gmail.com"),
                'smtp_port': int(os.getenv("SMTP_PORT", "587"))
            }
            self.discord_config = {
                'enabled': bool(os.getenv("DISCORD_WEBHOOK_URL")),
                'webhook_url': os.getenv("DISCORD_WEBHOOK_URL")
            }
            self.slack_config = {
                'enabled': bool(os.getenv("SLACK_WEBHOOK_URL")),
                'webhook_url': os.getenv("SLACK_WEBHOOK_URL")
            }
    
    def _validate_config(self):
        """Validate notification configuration"""
        issues = []
        
        # Check email configuration
        if self.email_config['enabled']:
            required_fields = ['from', 'to', 'password']
            missing = [field for field in required_fields if not self.email_config.get(field)]
            if missing:
                issues.append(f"Email: Missing required fields: {', '.join(missing)}")
        
        # Check Discord configuration
        if self.discord_config['enabled']:
            if not self.discord_config.get('webhook_url'):
                issues.append("Discord: Missing webhook URL")
        
        # Check Slack configuration
        if self.slack_config['enabled']:
            if not self.slack_config.get('webhook_url'):
                issues.append("Slack: Missing webhook URL")
        
        # Log validation results
        if issues:
            logger.warning("⚠️ Notification configuration issues:")
            for issue in issues:
                logger.warning(f"  {issue}")
        else:
            enabled_channels = []
            if self.email_config['enabled']: enabled_channels.append("Email")
            if self.discord_config['enabled']: enabled_channels.append("Discord")
            if self.slack_config['enabled']: enabled_channels.append("Slack")
            
            if enabled_channels:
                logger.info(f"✅ Notification channels enabled: {', '.join(enabled_channels)}")
            else:
                logger.warning("⚠️ No notification channels enabled")
    
    async def send_notification(self, subject: str, message: str, priority: str = "normal") -> Dict[str, Any]:
        """Send notification through all enabled channels"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "subject": subject,
            "priority": priority,
            "channels": {}
        }
        
        # Send email notification
        if self.email_config['enabled']:
            try:
                email_result = await self._send_email(subject, message)
                results["channels"]["email"] = email_result
            except Exception as e:
                logger.error(f"❌ Email notification failed: {e}")
                results["channels"]["email"] = {"status": "error", "error": str(e)}
        
        # Send Discord notification
        if self.discord_config['enabled']:
            try:
                discord_result = await self._send_discord(subject, message, priority)
                results["channels"]["discord"] = discord_result
            except Exception as e:
                logger.error(f"❌ Discord notification failed: {e}")
                results["channels"]["discord"] = {"status": "error", "error": str(e)}
        
        # Send Slack notification
        if self.slack_config['enabled']:
            try:
                slack_result = await self._send_slack(subject, message, priority)
                results["channels"]["slack"] = slack_result
            except Exception as e:
                logger.error(f"❌ Slack notification failed: {e}")
                results["channels"]["slack"] = {"status": "error", "error": str(e)}
        
        # Log summary
        successful_channels = [ch for ch, result in results["channels"].items() if result.get("status") == "success"]
        failed_channels = [ch for ch, result in results["channels"].items() if result.get("status") == "error"]
        
        if successful_channels:
            logger.info(f"✅ Notification sent via: {', '.join(successful_channels)}")
        if failed_channels:
            logger.warning(f"⚠️ Notification failed via: {', '.join(failed_channels)}")
        
        return results
    
    async def _send_email(self, subject: str, body: str) -> Dict[str, Any]:
        """Send email notification"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_config['from']
            msg['To'] = self.email_config['to']
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            
            # Create HTML and plain text versions
            html_body = self._convert_markdown_to_html(body)
            plain_body = self._convert_markdown_to_plain(body)
            
            # Attach parts
            text_part = MIMEText(plain_body, 'plain', 'utf-8')
            html_part = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp_email, msg)
            
            logger.info(f"✅ Email sent successfully to {self.email_config['to']}")
            return {"status": "success", "recipient": self.email_config['to']}
            
        except Exception as e:
            logger.error(f"❌ Email sending failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def _send_smtp_email(self, msg: MIMEMultipart):
        """Send email via SMTP (blocking operation)"""
        with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
            server.starttls()
            server.login(self.email_config['from'], self.email_config['password'])
            server.send_message(msg)
    
    async def _send_discord(self, subject: str, message: str, priority: str = "normal") -> Dict[str, Any]:
        """Send Discord webhook notification"""
        try:
            # Determine color based on priority and content
            color = self._get_discord_color(priority, subject)
            
            # Prepare Discord embed
            embed = {
                "title": subject,
                "description": message[:2000],  # Discord has 2000 char limit for description
                "color": color,
                "timestamp": datetime.now().isoformat(),
                "footer": {
                    "text": "LinkedIn Automation Bot"
                },
                "fields": []
            }
            
            # Add priority field if not normal
            if priority != "normal":
                embed["fields"].append({
                    "name": "Priority",
                    "value": priority.title(),
                    "inline": True
                })
            
            # Prepare payload
            payload = {
                "username": "LinkedIn Bot",
                "avatar_url": "https://cdn.jsdelivr.net/gh/devicons/devicon/icons/linkedin/linkedin-original.svg",
                "embeds": [embed]
            }
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.discord_config['webhook_url'],
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 204:
                        logger.info("✅ Discord notification sent successfully")
                        return {"status": "success", "platform": "Discord"}
                    else:
                        error_text = await response.text()
                        raise Exception(f"Discord API error {response.status}: {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ Discord notification failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _send_slack(self, subject: str, message: str, priority: str = "normal") -> Dict[str, Any]:
        """Send Slack webhook notification"""
        try:
            # Determine color based on priority
            color = self._get_slack_color(priority, subject)
            
            # Prepare Slack message
            payload = {
                "username": "LinkedIn Bot",
                "icon_emoji": ":briefcase:",
                "attachments": [
                    {
                        "color": color,
                        "title": subject,
                        "text": message,
                        "footer": "LinkedIn Automation Bot",
                        "ts": int(datetime.now().timestamp()),
                        "fields": []
                    }
                ]
            }
            
            # Add priority field if not normal
            if priority != "normal":
                payload["attachments"][0]["fields"].append({
                    "title": "Priority",
                    "value": priority.title(),
                    "short": True
                })
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_config['webhook_url'],
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        logger.info("✅ Slack notification sent successfully")
                        return {"status": "success", "platform": "Slack"}
                    else:
                        error_text = await response.text()
                        raise Exception(f"Slack API error {response.status}: {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ Slack notification failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def _get_discord_color(self, priority: str, subject: str) -> int:
        """Get Discord embed color based on priority and content"""
        if priority == "high" or "error" in subject.lower() or "failed" in subject.lower():
            return 0xE74C3C  # Red
        elif priority == "medium" or "warning" in subject.lower():
            return 0xF39C12  # Orange
        elif "success" in subject.lower() or "completed" in subject.lower():
            return 0x27AE60  # Green
        else:
            return 0x3498DB  # Blue
    
    def _get_slack_color(self, priority: str, subject: str) -> str:
        """Get Slack attachment color based on priority and content"""
        if priority == "high" or "error" in subject.lower() or "failed" in subject.lower():
            return "danger"
        elif priority == "medium" or "warning" in subject.lower():
            return "warning"
        elif "success" in subject.lower() or "completed" in subject.lower():
            return "good"
        else:
            return "#3498DB"
    
    def _convert_markdown_to_html(self, markdown_text: str) -> str:
        """Convert simple markdown to HTML for email"""
        html = markdown_text
        
        # Headers
        html = html.replace('### ', '<h3>').replace('\n# ', '</h3>\n<h1>').replace('\n## ', '</h1>\n<h2>').replace('\n### ', '</h2>\n<h3>')
        
        # Bold
        html = html.replace('**', '<strong>', 1).replace('**', '</strong>', 1)
        
        # Code blocks
        html = html.replace('```', '<pre><code>').replace('```', '</code></pre>')
        
        # Line breaks
        html = html.replace('\n', '<br>\n')
        
        # Wrap in basic HTML structure
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            {html}
        </body>
        </html>
        """
    
    def _convert_markdown_to_plain(self, markdown_text: str) -> str:
        """Convert markdown to plain text for email"""
        plain = markdown_text
        
        # Remove markdown formatting
        plain = plain.replace('**', '')
        plain = plain.replace('### ', '')
        plain = plain.replace('## ', '')
        plain = plain.replace('# ', '')
        plain = plain.replace('```', '')
        
        return plain
    
    async def send_automation_start(self) -> Dict[str, Any]:
        """Send notification when automation starts"""
        subject = "🚀 LinkedIn Automation Started"
        message = f"""
# LinkedIn Automation Started

**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** Starting daily automation sequence

The LinkedIn automation bot has started its daily tasks. You will receive another notification when the automation completes.

---
*This is an automated message from LinkedIn Automation Bot*
"""
        return await self.send_notification(subject, message, "normal")
    
    async def send_automation_complete(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification when automation completes"""
        successful_tasks = sum(1 for task in results.get("tasks", []) if task["result"]["status"] == "success")
        total_tasks = len(results.get("tasks", []))
        overall_status = results.get("overall_status", "unknown")
        
        # Determine priority based on results
        priority = "normal" if overall_status == "success" else "medium"
        
        subject = f"✅ LinkedIn Automation Complete - {overall_status.title()}"
        message = f"""
# LinkedIn Automation Complete

**Status:** {overall_status.title()}
**Tasks Completed:** {successful_tasks}/{total_tasks}
**Duration:** {results.get('start_time', 'Unknown')} - {results.get('end_time', 'Unknown')}

## Task Results:

"""
        
        for task in results.get("tasks", []):
            task_name = task["name"].replace("_", " ").title()
            task_status = task["result"]["status"]
            status_emoji = "✅" if task_status == "success" else "❌"
            
            message += f"### {status_emoji} {task_name}\n"
            message += f"**Status:** {task_status.title()}\n"
            
            if task_status == "success" and "file" in task["result"]:
                message += f"**Output File:** {task['result']['file']}\n"
            elif task_status == "error":
                message += f"**Error:** {task['result'].get('error', 'Unknown error')}\n"
            
            message += "\n"
        
        message += """
---
*This is an automated message from LinkedIn Automation Bot*
"""
        
        return await self.send_notification(subject, message, priority)
    
    async def send_error_alert(self, error_type: str, error_message: str, context: str = "") -> Dict[str, Any]:
        """Send high-priority error alert"""
        subject = f"🚨 LinkedIn Automation Error - {error_type}"
        message = f"""
# Critical Error Alert

**Error Type:** {error_type}
**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Context:** {context or 'General automation error'}

## Error Details:

```
{error_message}
```

**Action Required:** Please check the automation logs and configuration.

---
*This is an automated error alert from LinkedIn Automation Bot*
"""
        return await self.send_notification(subject, message, "high")
    
    async def test_notifications(self) -> Dict[str, Any]:
        """Test all notification channels"""
        subject = "🧪 LinkedIn Automation Test Notification"
        message = f"""
# Test Notification

**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is a test notification to verify that all notification channels are working correctly.

## Enabled Channels:
- **Email:** {'✅ Enabled' if self.email_config['enabled'] else '❌ Disabled'}
- **Discord:** {'✅ Enabled' if self.discord_config['enabled'] else '❌ Disabled'}
- **Slack:** {'✅ Enabled' if self.slack_config['enabled'] else '❌ Disabled'}

If you received this message, your notifications are working properly!

---
*This is a test message from LinkedIn Automation Bot*
"""
        
        logger.info("🧪 Sending test notifications...")
        result = await self.send_notification(subject, message, "normal")
        
        # Log test results
        successful_channels = [ch for ch, res in result["channels"].items() if res.get("status") == "success"]
        failed_channels = [ch for ch, res in result["channels"].items() if res.get("status") == "error"]
        
        logger.info(f"📊 Test Results - Success: {successful_channels}, Failed: {failed_channels}")
        
        return result

# Backward compatibility functions
async def send_email_notification(subject: str, body: str) -> bool:
    """Legacy function for backward compatibility"""
    try:
        notifier = NotificationManager()
        result = await notifier._send_email(subject, body)
        return result["status"] == "success"
    except Exception as e:
        logger.error(f"❌ Legacy email notification failed: {e}")
        return False

# Example usage and testing
async def main():
    """Test the notification manager"""
    try:
        notifier = NotificationManager()
        
        print("🧪 Testing LinkedIn Automation Notification Manager")
        print("=" * 60)
        
        # Test notifications
        result = await notifier.test_notifications()
        
        print(f"\n📊 Test Results:")
        for channel, res in result["channels"].items():
            status = "✅ Success" if res["status"] == "success" else f"❌ Failed: {res.get('error', 'Unknown')}"
            print(f"  {channel.title()}: {status}")
        
        # Test error notification
        print("\n🚨 Testing error notification...")
        await notifier.send_error_alert("Test Error", "This is a test error message", "Testing context")
        
        print("✅ Notification manager test completed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
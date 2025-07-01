# linkedin_bot/editor.py
import re
from ai_modules.linkedin_reader import get_profile_html, ask_ai_to_analyze
from linkedin_bot.browser import launch_browser

def extract_sections(ai_response: str):
    headline_match = re.search(r"Improved Headline:\s*(.+)", ai_response)
    about_match = re.search(r"Improved Summary:\s*([\s\S]+?)(?:\n[A-Z][a-z]+:|\Z)", ai_response)
    headline = headline_match.group(1).strip() if headline_match else ""
    about = about_match.group(1).strip() if about_match else ""
    return headline, about

async def update_profile():
    print("🔐 Logging in and accessing profile page...")
    html = await get_profile_html()
    if not html:
        print("❌ Could not fetch profile.")
        return

    print("🤖 Sending data to AI model...")
    ai_response = await ask_ai_to_analyze(html)
    headline, about = extract_sections(ai_response)

    browser, context, page = await launch_browser()
    await page.goto("https://www.linkedin.com/in/me/edit/topcard/", timeout=60000)
    await page.wait_for_timeout(5000)

    print("🚧 Replace the below CSS selectors manually after inspection.")
    print("📌 HEADLINE:", headline)
    print("📌 ABOUT:", about)

    # Placeholder: Replace CSS selectors
    # await page.fill("CSS_SELECTOR_HEADLINE", headline)
    # await page.fill("CSS_SELECTOR_ABOUT", about)
    # await page.click("CSS_SELECTOR_SAVE")

    await browser.close()
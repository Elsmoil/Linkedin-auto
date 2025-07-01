# linkedin_bot/browser.py
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os

load_dotenv()

async def launch_browser():
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")
    if email is None or password is None:
        raise ValueError("LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables must be set")

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    await page.goto("https://www.linkedin.com/login")
    await page.fill('input[name="session_key"]', email)
    await page.fill('input[name="session_password"]', password)
    await page.click('button[type="submit"]')
    await page.wait_for_timeout(5000)

    return browser, context, page
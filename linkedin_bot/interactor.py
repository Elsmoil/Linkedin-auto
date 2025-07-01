# linkedin_bot/interactor.py
from linkedin_bot.browser import launch_browser
import asyncio

async def interact_with_feed():
    browser, context, page = await launch_browser()
    await page.goto("https://www.linkedin.com/feed/")
    await page.wait_for_timeout(7000)

    print("✨ Auto-interacting with posts...")
    posts = await page.locator("article").all()

    for index, post in enumerate(posts[:5]):  # Interact with 5 posts
        try:
            like_button = await post.locator('button[aria-label*="Like"]').first
            await like_button.click()
            await page.wait_for_timeout(1000)

            comment_button = await post.locator('button[aria-label*="Comment"]').first
            await comment_button.click()
            await page.fill('textarea', "Great insight! Thanks for sharing.")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(1500)

            print(f"✅ Interacted with post {index + 1}")
        except Exception as e:
            print(f"⚠️ Failed to interact with post {index + 1}: {e}")

    await browser.close()
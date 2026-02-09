import asyncio
from playwright.async_api import async_playwright
import os

async def save_session():
    async with async_playwright() as p:
        # Launch browser in non-headless mode so user can interact
        browser = await p.chromium.launch(headless=False)
        
        # Create a new browser context
        context = await browser.new_context()
        
        page = await context.new_page()
        
        print("\n--- Sora Session Capturer ---")
        print("1. Opening Sora in a new browser window...")
        await page.goto("https://sora.com/login") # Direct login page
        
        print("\nACTION REQUIRED:")
        print("Please log in manually in the browser window that just opened.")
        print("Note: If you are in Bangladesh, make sure your VPN is active before logging in.")
        print("\nWaiting for you to reach the main Sora dashboard...")
        
        # Wait for the user to reach a URL that indicates they are logged in
        # Usually sora.com/profile or just sora.com with authenticated content
        await page.wait_for_url("**/profile**", timeout=0) # No timeout, wait forever for user
        
        print("\n✅ Logged in successfully!")
        print("Saving your session state to 'sora_automation/auth_state.json'...")
        
        # Ensure directory exists
        os.makedirs("sora_automation", exist_ok=True)
        
        # Save the cookies and local storage
        await context.storage_state(path="sora_automation/auth_state.json")
        
        print("\n🎉 SESSION SAVED!")
        print("You can now close the browser window. We will use this file for headless automation.")
        
        await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(save_session())
    except KeyboardInterrupt:
        print("\nExiting...")

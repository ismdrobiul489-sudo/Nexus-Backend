import asyncio
from playwright.async_api import async_playwright
import os
import time

# Path to the saved authentication state
AUTH_FILE = "sora_automation/auth_state.json"

async def generate_vids(prompt):
    if not os.path.exists(AUTH_FILE):
        print(f"❌ Error: {AUTH_FILE} not found. Please run save_session.py first!")
        return

    async with async_playwright() as p:
        # Launch browser (headless=True for Docker/Server)
        browser = await p.chromium.launch(headless=True)
        
        # Load the saved session state (Auth, Cookies, LocalStorage, etc.)
        context = await browser.new_context(storage_state=AUTH_FILE)
        page = await context.new_page()
        
        print(f"\n🎬 Starting Headless Generation for: '{prompt}'...")
        await page.goto("https://sora.com")
        
        # Check if we are actually logged in
        if "login" in page.url:
            print("❌ Error: Session expired. Please run save_session.py again.")
            await browser.close()
            return

        try:
            # 1. Find the prompt textarea or input
            # Based on standard Sora UI, look for textarea or specific class
            print("✏️ Entering prompt...")
            textarea = page.locator('textarea[placeholder*="Describe"], textarea[placeholder*="What"], textarea').first
            await textarea.fill(prompt)
            
            # 2. Click the Generate/Create button
            # Button usually has 'Create' or a specific icon
            print("🚀 Clicking Create...")
            create_btn = page.locator('button:has-text("Create"), button:has-text("Generate"), button[type="submit"]').first
            await create_btn.click()
            
            print("⏳ Video task submitted! Waiting for progress...")
            
            # 3. Wait for progress to appear and complete
            # We can poll the UI or wait for a specific element
            # For simplicity, we wait for the video player or download button to appear
            # or a selector that represents 'Completed'
            
            # This is a simplified wait. In real usage, you might poll for 'status: succeeded'
            await page.wait_for_timeout(5000) # Give it a few seconds to start
            
            print("ℹ️ Polling UI for completion (Estimated 2-5 mins)...")
            # Loop to check for completion
            for _ in range(60): # 10 minutes max
                if await page.locator('button:has-text("Download"), a:has-text("Download")').count() > 0:
                    print("\n🎉 VIDEO READY!")
                    # Just an example of how to interact once ready
                    break
                await page.wait_for_timeout(10000) # Wait 10s
                print(".", end="", flush=True)
            
            print("\n✅ Task finished in headless mode.")
                
        except Exception as e:
            print(f"❌ Automation Error: {e}")
            # Screenshot for debugging in headless environment
            await page.screenshot(path="sora_automation/error_debug.png")
            print("Captured error screenshot: sora_automation/error_debug.png")
        
        await browser.close()

if __name__ == "__main__":
    prompt = input("Prompt: ").strip() or "A cinematic view of London"
    asyncio.run(generate_vids(prompt))

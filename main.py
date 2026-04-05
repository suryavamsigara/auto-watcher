import asyncio
import re
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from helpers import parse_duration_and_wait, play_video

# ================= CONFIGURATION =================
BROWSER_PROFILE_DIR = os.path.join(os.getcwd(), "browser_profiles", "default")
# =================================================

async def main():
    print("🚀 Starting Auto-Watcher...")
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)

    playwright = await async_playwright().start()
    context = await playwright.chromium.launch_persistent_context(
        BROWSER_PROFILE_DIR,
        headless=False,
        no_viewport=True,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
    )
    
    page = context.pages[0] if context.pages else await context.new_page()

    print("🌐 Navigating to portal...")
    await page.goto("https://cdc.vit.ac.in/mycourses?type=mycourses", wait_until="domcontentloaded")
    
    print("🔍 Checking login status...")
    try:
        # Quick check: If you are already logged in, the courses will load within 5 seconds.
        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=5000)
        print("✅ Active session found. Proceeding directly to courses...")
        
    except PlaywrightTimeoutError:
        # If it times out, the user is likely on the login screen.
        print("⚠️ Authentication required. Please log in manually in the browser window.")
        print("⏳ Script is paused and waiting for you to complete login... (Timeout: 5 minutes)")
        
        await page.wait_for_url(re.compile(r"dashboard|mycourses", re.IGNORECASE), timeout=300000)
        print("✅ Login successful!")
        
        # If the portal routes to the dashboard, force a redirect to the courses page
        if "mycourses" not in page.url:
            print("🌐 Redirecting from Dashboard to My Courses...")
            await page.goto("https://cdc.vit.ac.in/mycourses?type=mycourses", wait_until="domcontentloaded")
            
        # Wait for the course cards to finally load
        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=15000)
        
    await page.wait_for_timeout(2000)

    # =================================================
    # STEP 1: Scrape Courses and Present CLI Menu
    # =================================================
    course_elements = await page.locator("div[aria-labelledby='course-name']").all()
    print("\n" + "="*40)
    print("📚 AVAILABLE COURSES")
    print("="*40)
    
    for i, el in enumerate(course_elements):
        title = await el.inner_text()
        print(f"[{i + 1}] {title.strip()}")
        
    print("="*40)
    
    while True:
        try:
            choice = int(input("\nEnter the number of the course you want to complete: "))
            if 1 <= choice <= len(course_elements):
                break
            print("❌ Invalid number. Try again.")
        except ValueError:
            print("❌ Please enter a valid integer.")

    selected_index = choice - 1
    selected_course_title = await course_elements[selected_index].inner_text()
    
    print(f"\n🖱️ Opening Course: {selected_course_title}")
    await course_elements[selected_index].click(force=True)
    
    print("⏳ Waiting for modules to render...")
    await page.wait_for_selector("div[aria-labelledby='sidebar-module']", timeout=30000)
    await page.wait_for_timeout(4000)

    # =================================================
    # STEP 2: Iterate Through Modules
    # =================================================
    modules = page.locator("div[aria-labelledby='sidebar-module']")
    module_count = await modules.count()
    
    print(f"\n📦 Found {module_count} Modules.")

    for m in range(module_count):
        current_mod = page.locator("div[aria-labelledby='sidebar-module']").nth(m)
        
        mod_title_el = current_mod.locator("div.t-ml-15").first
        mod_title = await mod_title_el.inner_text()
        
        print(f"\n" + "="*40)
        print(f"🔄 Processing Module {m+1}/{module_count}: {mod_title.strip()}")
        print("="*40)
        
        # Expand the main module if it has a down-arrow
        main_arrow = current_mod.locator("div.accordHeadright").first.locator("img[alt='down-arrow']")
        if await main_arrow.count() > 0:
            await main_arrow.click(force=True)
            await page.wait_for_timeout(2000)

        # =================================================
        # STEP 3: STRICTLY target "Learning Contents"
        # =================================================
        lc_section = current_mod.locator("div.submod").filter(has_text=re.compile(r"Learning Contents", re.IGNORECASE)).first
        
        if await lc_section.count() == 0:
            print("   No 'Learning Contents' section found. Skipping module...")
            # Collapse the main module to keep DOM clean
            main_up_arrow = current_mod.locator("div.accordHeadright").first.locator("img[alt='up-arrow']")
            if await main_up_arrow.count() > 0:
                await main_up_arrow.click(force=True)
                await page.wait_for_timeout(500)
            continue
            
        # Expand "Learning Contents" if it has a down-arrow
        lc_arrow = lc_section.locator("div.accordHeadright img[alt='down-arrow']")
        if await lc_arrow.count() > 0:
            await lc_arrow.click(force=True)
            await page.wait_for_timeout(1000)

        # =================================================
        # STEP 4: Iterate Through Videos (Only in Learning Contents)
        # =================================================
        # Look for video rows strictly inside our lc_section
        topics = lc_section.locator(".accEach1")
        topic_count = await topics.count()
        
        if topic_count == 0:
            print("   No video topics found in 'Learning Contents'. Moving to next module...")
        else:
            print(f"\n   Found {topic_count} topics in Learning Contents. Starting playback loop...")
            
            for t in range(topic_count):
                # Re-query locator to avoid stale elements
                current_topic = current_mod.locator("div.submod").filter(has_text=re.compile(r"Learning Contents", re.IGNORECASE)).first.locator(".accEach1").nth(t)
                
                await current_topic.scroll_into_view_if_needed()
                
                topic_text = await current_topic.inner_text()
                clean_title = topic_text.replace("\n", " - ").strip()
                print(f"\n📺 Opening Topic {t+1}/{topic_count}: {clean_title}")
                
                await current_topic.click(force=True)
                await page.wait_for_timeout(3000) 
                
                await play_video(page)
                await parse_duration_and_wait(topic_text)

        # Cleanup: Collapse the main module to keep the DOM clean
        main_up_arrow = current_mod.locator("div.accordHeadright").first.locator("img[alt='up-arrow']")
        if await main_up_arrow.count() > 0:
            await main_up_arrow.click(force=True)
            await page.wait_for_timeout(500)

    print("\n🎉 You have watched videos in all modules of this course successfully!")
    print("\nRestart the script to complete another course.")
    await context.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())

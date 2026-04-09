import asyncio
import re
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from helpers import parse_duration_and_wait, play_video

BROWSER_PROFILE_DIR = os.path.join(os.getcwd(), "browser_profiles", "default")

async def main():
    print("🚀 Starting Auto-Watcher...")
    os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)

    # Launch persistent chrome browser
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
        # The courses will load within 5 seconds if logged in.
        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=5000)
        print("✅ Active session found. Proceeding directly to courses...")
        
    except PlaywrightTimeoutError:
        # If it times out, the user is likely on the login screen.
        print("⚠️ Authentication required. Script is paused and waiting for you to complete login... (Timeout: 5 minutes)")
        
        await page.wait_for_url(re.compile(r"dashboard|mycourses", re.IGNORECASE), timeout=300000)
        print("✅ Login successful!")
        
        # If the portal routes to the dashboard, force a redirect to the courses page
        if "mycourses" not in page.url:
            print("🌐 Redirecting from Dashboard to My Courses...")
            await page.goto("https://cdc.vit.ac.in/mycourses?type=mycourses", wait_until="domcontentloaded")
            
        # Wait for the course cards to finally load
        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=15000)
        
    await page.wait_for_timeout(2000)

    # Scrape Courses and Present CLI Menu
    course_elements = await page.locator("div[aria-labelledby='course-name']").all()
    print("\n" + "="*50)
    print("📚 AVAILABLE COURSES")
    print("="*50)
    
    for i, el in enumerate(course_elements):
        title = await el.inner_text()
        print(f"[{i + 1}] {title.strip()}")
        
    print("="*50)
    
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

    # Iterate Through Modules
    modules = page.locator("div[aria-labelledby='sidebar-module']")
    module_count = await modules.count()
    
    print(f"\n📦 Found {module_count} Modules.")

    module_start = 1

    # Asking the user whether to start from a specif module
    while True:
        start_input = input("\nEnter a specific module number to start from (or press Enter to start from 1): ").strip()

        if not start_input:
            print("\nStarting from the first module...")
            break

        try:
            module_start = int(start_input)
            if 1 <= module_start <= module_count:
                print(f"Continuing from module: {module_start}")
                break
            else:
                print(f"❌ Please enter a number between 1 and {module_count}.")
        except ValueError:
            print("❌ Please enter a valid number")

    for m in range(module_start - 1, module_count):
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

        # Process Video Sections Dynamically
        target_headers = current_mod.locator("div.accordHeadright").filter(has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE))
        header_count = await target_headers.count()

        if header_count > 0:
            for h in range(header_count):
                # Re-query the header to prevent stale element references
                header = current_mod.locator("div.accordHeadright").filter(has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE)).nth(h)
                
                section_title = await header.inner_text()
                print(f"\n   📂 Processing section: {section_title.strip()}")
                
                # Expand section if it has a down-arrow
                arrow = header.locator("img[alt='down-arrow']")
                if await arrow.count() > 0:
                    await arrow.click(force=True)
                    await page.wait_for_timeout(2000)
                
                # Scope strictly to this section's wrapper to avoid clicking hidden videos elsewhere
                section_wrapper = header.locator("xpath=ancestor::div[contains(@class, 'submod')][1]")
                
                topics = section_wrapper.locator(".accEach1")
                topic_count = await topics.count()
                
                if topic_count == 0:
                    print(f"      No videos found in {section_title.strip()}.")
                else:
                    for t in range(topic_count):

                        # Check if the main module collapsed
                        main_arrow_check = current_mod.locator("div.accordHeadright").first.locator("img[alt='down-arrow']")
                        if await main_arrow_check.count() > 0:
                            await main_arrow_check.click(force=True)
                            await page.wait_for_timeout(1000)

                        # Check if the sub section collapsed
                        sub_header_check = current_mod.locator("div.accordHeadright").filter(has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE)).nth(h)
                        sub_arrow_check = sub_header_check.locator("img[alt='down-arrow']")
                        if await sub_arrow_check.count() > 0:
                            await sub_arrow_check.click(force=True)
                            await page.wait_for_timeout(1000)

                        # Re-query topic dynamically to avoid stale elements
                        current_topic = current_mod.locator("div.accordHeadright").filter(has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE)).nth(h).locator("xpath=ancestor::div[contains(@class, 'submod')][1]").locator(".accEach1").nth(t)
                        
                        await current_topic.scroll_into_view_if_needed()
                        topic_text = await current_topic.inner_text()
                        clean_title = topic_text.replace("\n", " - ").strip()
                        
                        print(f"\n     📺 Opening Topic {t+1}/{topic_count}: {clean_title}")
                        
                        await current_topic.click(force=True)
                        await page.wait_for_timeout(2000)
                        
                        await play_video(page)
                        await parse_duration_and_wait(topic_text)

        # -------------------------------------------------
        # FALLBACK: If NO named sections existed, check directly under the module
        # -------------------------------------------------
        else:
            topics = current_mod.locator(".accEach1")
            topic_count = await topics.count()
            
            if topic_count > 0:
                print(f"\n   📂 Found {topic_count} videos directly under the module.")
                for t in range(topic_count):
                    current_topic = current_mod.locator(".accEach1").nth(t)
                    
                    await current_topic.scroll_into_view_if_needed()
                    topic_text = await current_topic.inner_text()
                    clean_title = topic_text.replace("\n", " - ").strip()
                    
                    print(f"\n      📺 Opening Topic {t+1}/{topic_count}: {clean_title}")
                    
                    await current_topic.click(force=True)
                    await page.wait_for_timeout(2000)
                    
                    await play_video(page)
                    await parse_duration_and_wait(topic_text)
            else:
                print("   No video topics found anywhere in this module. Moving to next...")

        # Cleanup: Collapse the main module to keep the DOM clean
        main_up_arrow = current_mod.locator("div.accordHeadright").first.locator("img[alt='up-arrow']")
        if await main_up_arrow.count() > 0:
            await main_up_arrow.click(force=True)
            await page.wait_for_timeout(2000)

    print("\n🎉 You have watched videos in all modules of this course successfully!")
    print("\nRestart the script to complete another course.")
    await context.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(main())

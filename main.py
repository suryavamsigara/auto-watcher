import asyncio
import re
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from helpers import parse_duration_and_wait, play_video

BROWSER_PROFILE_DIR = os.path.join(os.getcwd(), "browser_profiles", "default")


def _parse_selection(raw: str, max_count: int, item_label: str) -> list[int] | None:
    raw = raw.strip()

    if not raw:
        return list(range(max_count))

    if raw.endswith("*"):
        num_str = raw[:-1]
        if not num_str.isdigit():
            print(f"❌ Invalid entry: '{raw}' — enter a number before *")
            return None
        num = int(num_str)
        if num < 1 or num > max_count:
            print(f"❌ {item_label.capitalize()} {num} does not exist. Available {item_label}s: 1-{max_count}")
            return None
        return list(range(num - 1, max_count))

    if "," in raw:
        tokens = [t.strip() for t in raw.split(",")]
        invalid = []
        result = []

        for t in tokens:
            if t.endswith("*"):
                print(f"❌ Cannot mix range ({t}) with comma-separated list.")
                return None
            if not t.isdigit():
                invalid.append(t)
                continue
            num = int(t)
            if num < 1 or num > max_count:
                invalid.append(t)
                continue
            result.append(num - 1)

        if invalid:
            print(f"❌ Invalid entries: {', '.join(invalid)}")
            return None
        return sorted(set(result))

    if not raw.isdigit():
        print(f"❌ '{raw}' is not a valid number.")
        return None

    num = int(raw)
    if num < 1 or num > max_count:
        print(f"❌ {item_label.capitalize()} {num} does not exist. Available {item_label}s: 1-{max_count}")
        return None
    return [num - 1]


def parse_course_selection(raw: str, max_count: int) -> list[int] | None:
    return _parse_selection(raw, max_count, "course")


def parse_module_selection(raw: str, max_count: int) -> list[int] | None:
    return _parse_selection(raw, max_count, "module")


async def ensure_on_course_list(page):
    print("🌐 Returning to course list...")
    await page.goto("https://cdc.vit.ac.in/mycourses?type=mycourses", wait_until="domcontentloaded")
    try:
        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=15000)
    except PlaywrightTimeoutError:
        print("⚠️ Course list didn't load. Trying login recovery...")
        await page.wait_for_url(re.compile(r"dashboard|mycourses", re.IGNORECASE), timeout=60000)
        if "mycourses" not in page.url:
            print("🌐 Redirecting from Dashboard to My Courses...")
            await page.goto("https://cdc.vit.ac.in/mycourses?type=mycourses", wait_until="domcontentloaded")
        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=15000)
    await page.wait_for_timeout(2000)
    return await page.locator("div[aria-labelledby='course-name']").all()


async def collect_module_input(page, course_title: str):
    print("⏳ Waiting for modules to render...")
    try:
        await page.wait_for_selector("div[aria-labelledby='sidebar-module']", timeout=30000)
    except PlaywrightTimeoutError:
        print(f"⚠️ No modules found for \"{course_title}\". Skipping.")
        return None

    await page.wait_for_timeout(4000)

    modules = page.locator("div[aria-labelledby='sidebar-module']")
    module_count = await modules.count()

    if module_count == 0:
        print(f"⚠️ No modules found for \"{course_title}\". Skipping.")
        return None

    print(f"\n📦 Found {module_count} Modules in \"{course_title}\".")

    module_titles = []
    for m in range(module_count):
        mod_el = modules.nth(m)
        mod_title_el = mod_el.locator("div.t-ml-15").first
        mod_title = await mod_title_el.inner_text()
        module_titles.append(mod_title.strip())

    print(f"\n📚 AVAILABLE MODULES FOR \"{course_title}\"")
    print("=" * 50)
    for m, title in enumerate(module_titles):
        print(f"[{m + 1}] {title}")
    print("=" * 50)

    while True:
        print(f"\n📦 MODULE SELECTION — \"{course_title}\"")
        print("Enter module numbers to process:")
        print("  • Comma-separated:  1,3,5     → modules 1, 3, and 5 only")
        print("  • Single number:    3         → only module 3")
        print("  • Range:            3*        → from module 3 to the end")
        print("  • Press Enter:                → from module 1 to the end")
        start_input = input("\nYour choice: ").strip()

        selected_modules = parse_module_selection(start_input, module_count)
        if selected_modules is not None:
            break

    return (module_titles, selected_modules, module_count)


async def process_course_modules(page, course_num: int, course_total: int, course_title: str,
                                  module_titles: list[str], selected_modules: list[int],
                                  module_count: int):
    sel_titles = [f"[{m + 1}] {module_titles[m]}" for m in selected_modules]
    print(f"📋 Processing {len(selected_modules)}/{module_count} modules: {', '.join(sel_titles)}")

    for m in selected_modules:
        current_mod = page.locator("div[aria-labelledby='sidebar-module']").nth(m)

        await current_mod.scroll_into_view_if_needed()
        await page.wait_for_timeout(1000)

        mod_title = module_titles[m]

        print(f"\n" + "=" * 40)
        print(f"🔄 Processing Module {m + 1}/{module_count}: {mod_title}")
        print("=" * 40)

        main_arrow = current_mod.locator("div.accordHeadright").first.locator("img[alt='down-arrow']")
        if await main_arrow.count() > 0:
            await main_arrow.click(force=True)
            await page.wait_for_timeout(2000)

        target_headers = current_mod.locator("div.accordHeadright").filter(
            has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE)
        )
        header_count = await target_headers.count()

        if header_count > 0:
            for h in range(header_count):
                header = current_mod.locator("div.accordHeadright").filter(
                    has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE)
                ).nth(h)

                section_title = await header.inner_text()
                print(f"\n   📂 Processing section: {section_title.strip()}")

                arrow = header.locator("img[alt='down-arrow']")
                if await arrow.count() > 0:
                    await arrow.click(force=True)
                    await page.wait_for_timeout(2000)

                section_wrapper = header.locator("xpath=ancestor::div[contains(@class, 'submod')][1]")
                topics = section_wrapper.locator(".accEach1")
                topic_count = await topics.count()

                if topic_count == 0:
                    print(f"      No videos found in {section_title.strip()}.")
                else:
                    for t in range(topic_count):
                        main_arrow_check = current_mod.locator("div.accordHeadright").first.locator("img[alt='down-arrow']")
                        if await main_arrow_check.count() > 0:
                            await main_arrow_check.click(force=True)
                            await page.wait_for_timeout(1000)

                        sub_header_check = current_mod.locator("div.accordHeadright").filter(
                            has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE)
                        ).nth(h)
                        sub_arrow_check = sub_header_check.locator("img[alt='down-arrow']")
                        if await sub_arrow_check.count() > 0:
                            await sub_arrow_check.click(force=True)
                            await page.wait_for_timeout(1000)

                        current_topic = current_mod.locator("div.accordHeadright").filter(
                            has_text=re.compile(r"Learning Content|Reference Video|Learning Video", re.IGNORECASE)
                        ).nth(h).locator(
                            "xpath=ancestor::div[contains(@class, 'submod')][1]"
                        ).locator(".accEach1").nth(t)

                        await current_topic.scroll_into_view_if_needed()
                        topic_text = await current_topic.inner_text()
                        clean_title = topic_text.replace("\n", " - ").strip()

                        print(f"\n     📺 Opening Topic {t + 1}/{topic_count}: {clean_title}")

                        await current_topic.click(force=True)
                        await page.wait_for_timeout(2000)

                        await play_video(page)
                        await parse_duration_and_wait(topic_text)

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

                    print(f"\n      📺 Opening Topic {t + 1}/{topic_count}: {clean_title}")

                    await current_topic.click(force=True)
                    await page.wait_for_timeout(2000)

                    await play_video(page)
                    await parse_duration_and_wait(topic_text)
            else:
                print("   No video topics found anywhere in this module. Moving to next...")

        main_up_arrow = current_mod.locator("div.accordHeadright").first.locator("img[alt='up-arrow']")
        if await main_up_arrow.count() > 0:
            await main_up_arrow.click(force=True)
            await page.wait_for_timeout(2000)

    print(f"\n✅ Completed ({course_num}/{course_total}): {course_title}")


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
        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=5000)
        print("✅ Active session found. Proceeding directly to courses...")
    except PlaywrightTimeoutError:
        print("⚠️ Authentication required. Script is paused and waiting for you to complete login... (Timeout: 5 minutes)")
        await page.wait_for_url(re.compile(r"dashboard|mycourses", re.IGNORECASE), timeout=300000)
        print("✅ Login successful!")

        if "mycourses" not in page.url:
            print("🌐 Redirecting from Dashboard to My Courses...")
            await page.goto("https://cdc.vit.ac.in/mycourses?type=mycourses", wait_until="domcontentloaded")

        await page.wait_for_selector("div[aria-labelledby='course-name']", timeout=15000)

    await page.wait_for_timeout(2000)

    course_elements = await page.locator("div[aria-labelledby='course-name']").all()
    print("\n" + "=" * 50)
    print("📚 AVAILABLE COURSES")
    print("=" * 50)

    course_titles = []
    for i, el in enumerate(course_elements):
        title = await el.inner_text()
        course_titles.append(title.strip())
        print(f"[{i + 1}] {title.strip()}")
    print("=" * 50)

    while True:
        print("\n📚 COURSE SELECTION")
        print("Enter course numbers to complete:")
        print("  • Comma-separated:  1,3,5     → courses 1, 3, and 5 only")
        print("  • Single number:    3         → only course 3")
        print("  • Range:            3*        → from course 3 to the end")
        print("  • Press Enter:                → from course 1 to the end")
        choice = input("\nYour choice: ").strip()

        selected_indices = parse_course_selection(choice, len(course_elements))
        if selected_indices is not None:
            break

    sel_titles = [f"[{i + 1}] {course_titles[i]}" for i in selected_indices]
    print(f"\n📋 Selected {len(selected_indices)}/{len(course_elements)} courses: {', '.join(sel_titles)}")

    # ─── Phase 1: Collect all module inputs ───────────────────────

    course_data = {}

    for course_num, idx in enumerate(selected_indices, 1):
        if course_num > 1:
            course_elements = await ensure_on_course_list(page)

        course_title = course_titles[idx]
        print(f"\n🖱️ Opening Course ({course_num}/{len(selected_indices)}): {course_title}")
        await course_elements[idx].click(force=True)

        result = await collect_module_input(page, course_title)
        if result is not None:
            course_data[idx] = result

    if not course_data:
        print("\n⚠️ None of the selected courses have any modules to process. Exiting.")
        await context.close()
        await playwright.stop()
        return

    # ─── Phase 2: Process all videos ──────────────────────────────

    total_with_modules = len(course_data)
    print(f"\n🎬 Starting video processing for {total_with_modules} course(s)...")

    for course_num, idx in enumerate(course_data.keys(), 1):
        course_elements = await ensure_on_course_list(page)

        course_title = course_titles[idx]
        print(f"\n🖱️ Opening Course ({course_num}/{total_with_modules}): {course_title}")
        await course_elements[idx].click(force=True)

        await page.wait_for_selector("div[aria-labelledby='sidebar-module']", timeout=30000)
        await page.wait_for_timeout(4000)

        module_titles, selected_modules, module_count = course_data[idx]
        await process_course_modules(page, course_num, total_with_modules, course_title,
                                      module_titles, selected_modules, module_count)

    print("\n🎉 All selected courses completed successfully!")
    await context.close()
    await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())

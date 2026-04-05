import re
import asyncio
from playwright.async_api import Page

WAIT_EXTRA_SECONDS = 30 # Add 30 seconds buffer to the video duration

async def parse_duration_and_wait(topic_text: str):
    """Extracts mm:ss from the topic text and waits that duration + 60 seconds."""
    match = re.search(r'(\d{2}):(\d{2})', topic_text)
    if not match:
        print(f"⚠️ Could not find duration in text. Defaulting to 5 minutes.")
        await asyncio.sleep(300)
        return

    minutes = int(match.group(1))
    seconds = int(match.group(2))
    total_video_seconds = (minutes * 60) + seconds
    
    # wait_time = total_video_seconds + WAIT_EXTRA_SECONDS

    wait_time = 5
    
    print(f"⏳ Found duration {minutes:02d}:{seconds:02d}. Waiting {wait_time} seconds (including 1m buffer)...")
    
    for remaining in range(wait_time, 0, -10):
        if remaining % 60 == 0 and remaining != wait_time:
            print(f"   ... {remaining // 60} minutes remaining")
        await asyncio.sleep(min(10, remaining))
        
    print("✅ Video complete!")

async def play_video(page: Page):
    """Handles clicking the specific video player overlay."""
    print("▶️ Attempting to click play button...")
    play_btn_selector = "#videoContainer0 div.t-cursor-pointer"
    
    try:
        await page.wait_for_selector(play_btn_selector, timeout=5000)
        await page.locator(play_btn_selector).first.click(force=True)
        print("✅ Play button clicked.")
    except Exception:
        print("⚠️ Play button not found or already playing.")
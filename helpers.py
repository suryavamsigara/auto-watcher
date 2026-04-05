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
    """Handles clicking the specific video player overlay (Vimeo or YouTube)."""
    print("▶️ Waiting for video player to initialize...")
    await page.wait_for_timeout(3000) 
    
    container_sel = "#videoContainer0"
    
    try:
        # Wait for the main video area to appear
        await page.wait_for_selector(container_sel, timeout=5000)
        
        # Force the browser to scroll the video dead-center to avoid viewport errors
        await page.locator(container_sel).evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")
        await page.wait_for_timeout(1000) 
        
        # Check which type of player is loaded
        yt_wrapper = page.locator(f"{container_sel} .youtube").first
        overlay = page.locator(f"{container_sel} div.t-cursor-pointer").first
        
        if await yt_wrapper.count() > 0:
            print("🎥 YouTube player detected. Executing double-tap strategy...")
            
            # Clicking the center of the container to dismiss the facade
            await page.locator(container_sel).click(force=True)
            print("   👆 First click executed (Loading player)...")
            
            # Waiting 2 seconds for the iframe to swap in and become interactive
            await page.wait_for_timeout(2000)
            
            # Click the center of the container again to hit the YouTube play button
            await page.locator(container_sel).click(force=True)
            print("✅ 👆 Second click executed (Video playing).")
            
        elif await overlay.count() > 0:
            print("🎥 Vimeo player detected.")
            # Click the center of the container for Vimeo
            await page.locator(container_sel).click(force=True)
            print("✅ Vimeo Play button clicked.")
            
        else:
            # Fallback
            await page.locator(container_sel).click(force=True)
            print("✅ Clicked main video container.")
            
    except Exception as e:
        print(f"⚠️ Play button interaction failed. Error: {str(e)[:100]}")
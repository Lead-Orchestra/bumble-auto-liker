#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bumble HTML Debugger
Simple script to log in, save HTML, and inspect page structure
"""

import sys
import json
import time
from pathlib import Path

try:
    import undetected_chromedriver as uc
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError as e:
    print(f"[X] Error: Missing required package: {e}")
    sys.exit(1)

def load_cookies_from_file(cookie_file: str):
    """Load cookies from JSON file"""
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        return cookies
    except Exception as e:
        print(f"[X] Error loading cookies: {e}")
        return None

def inject_cookies_to_browser(browser, cookies):
    """Inject cookies into the browser session"""
    try:
        browser.get("https://www.bumble.com")
        time.sleep(3)
        
        injected_count = 0
        for cookie in cookies:
            try:
                if 'sameSite' not in cookie:
                    cookie['sameSite'] = 'None'
                if 'expiry' in cookie and cookie['expiry'] is None:
                    del cookie['expiry']
                if 'domain' in cookie and not cookie['domain'].startswith('.'):
                    if '.' in cookie['domain']:
                        cookie['domain'] = f".{cookie['domain']}"
                browser.add_cookie(cookie)
                injected_count += 1
            except Exception:
                pass
        
        browser.refresh()
        time.sleep(3)
        return True
    except Exception as e:
        print(f"[!] Error injecting cookies: {e}")
        return False

def main():
    cookie_file = 'Scraper/bumble_cookies.json'
    if len(sys.argv) > 1:
        cookie_file = sys.argv[1]
    
    print("[*] Starting browser (visible mode)...")
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    browser = uc.Chrome(options=options, version_main=None, headless=False)
    browser.maximize_window()
    
    try:
        # Load and inject cookies
        print("[*] Loading cookies...")
        cookies = load_cookies_from_file(cookie_file)
        if cookies:
            print(f"[OK] Loaded {len(cookies)} cookies")
            inject_cookies_to_browser(browser, cookies)
        
        # Navigate to app
        print("[*] Navigating to Bumble app...")
        browser.get("https://www.bumble.com/app")
        time.sleep(5)
        
        print(f"[*] Current URL: {browser.current_url}")
        print(f"[*] Page title: {browser.title}")
        
        # Save HTML
        html_file = 'bumble_debug_page.html'
        print(f"[*] Saving HTML to {html_file}...")
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(browser.page_source)
        print(f"[OK] HTML saved to {html_file}")
        
        # Inspect page structure
        print("\n[*] Inspecting page structure...")
        print(f"[*] Page source length: {len(browser.page_source)} characters")
        
        # Find all buttons
        buttons = browser.find_elements(By.TAG_NAME, 'button')
        print(f"[*] Found {len(buttons)} button(s)")
        for i, btn in enumerate(buttons[:10]):  # First 10
            try:
                text = btn.text[:50] if btn.text else "No text"
                classes = btn.get_attribute('class')[:50] if btn.get_attribute('class') else "No class"
                testid = btn.get_attribute('data-testid') or "No testid"
                aria_label = btn.get_attribute('aria-label') or "No aria-label"
                print(f"  Button {i}: text='{text}' | class='{classes}' | testid='{testid}' | aria-label='{aria_label}'")
            except:
                pass
        
        # Find articles
        articles = browser.find_elements(By.TAG_NAME, 'article')
        print(f"\n[*] Found {len(articles)} article(s)")
        for i, article in enumerate(articles[:5]):
            try:
                classes = article.get_attribute('class')[:100] if article.get_attribute('class') else "No class"
                testid = article.get_attribute('data-testid') or "No testid"
                text_preview = article.text[:100] if article.text else "No text"
                print(f"  Article {i}: class='{classes}' | testid='{testid}' | text='{text_preview}...'")
            except:
                pass
        
        # Find main elements
        mains = browser.find_elements(By.TAG_NAME, 'main')
        print(f"\n[*] Found {len(mains)} main element(s)")
        
        # Find all elements with "encounters" in class or id
        encounter_elements = browser.find_elements(By.XPATH, "//*[contains(@class, 'encounters') or contains(@id, 'encounters') or contains(@data-testid, 'encounters')]")
        print(f"\n[*] Found {len(encounter_elements)} element(s) with 'encounters' in class/id/testid")
        for i, elem in enumerate(encounter_elements[:10]):
            try:
                tag = elem.tag_name
                classes = elem.get_attribute('class')[:100] if elem.get_attribute('class') else "No class"
                testid = elem.get_attribute('data-testid') or "No testid"
                print(f"  {tag} {i}: class='{classes}' | testid='{testid}'")
            except:
                pass
        
        # Wait for user to inspect
        print("\n[*] Browser will stay open for 60 seconds for manual inspection...")
        print("[*] Check the browser window and the saved HTML file")
        time.sleep(60)
        
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
    except Exception as e:
        print(f"[X] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[*] Closing browser...")
        browser.quit()

if __name__ == '__main__':
    main()



#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bumble Profile Scraper
Extracts profile data from visible Bumble profiles and automatically swipes right
Extracts data BEFORE swiping to capture all visible profiles
"""

import sys
import json
import csv
import argparse
import os
import time
import random
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

try:
    import undetected_chromedriver as uc
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
except ImportError as e:
    print(f"[X] Error: Missing required package: {e}")
    print("[+] Please install requirements: cd .. && uv pip install selenium undetected-chromedriver")
    sys.exit(1)

# Color output (simple ASCII for cross-platform compatibility)
GREEN = "[OK]"
RED = "[X]"
YELLOW = "[!]"
CYAN = "[*]"


def load_cookies_from_file(cookie_file: str) -> Optional[List[Dict]]:
    """Load cookies from JSON file extracted by extract_bumble_cookies.py"""
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        if not isinstance(cookies, list):
            print(f"{RED} Error: Invalid cookie file format. Expected a JSON array")
            return None
        
        if not cookies:
            print(f"{YELLOW} Warning: Cookie file is empty")
            return None
        
        print(f"{GREEN} Loaded {len(cookies)} cookies from {cookie_file}")
        return cookies
    except FileNotFoundError:
        print(f"{RED} Error: Cookie file not found: {cookie_file}")
        return None
    except json.JSONDecodeError as e:
        print(f"{RED} Error: Invalid JSON in cookie file: {e}")
        return None
    except Exception as e:
        print(f"{RED} Error: Failed to load cookies: {e}")
        return None


def inject_cookies_to_browser(browser: webdriver.Chrome, cookies: List[Dict]) -> bool:
    """Inject cookies into the browser session"""
    try:
        # Navigate to Bumble first (required for Selenium cookie injection)
        print(f"{CYAN} Navigating to Bumble to inject cookies...")
        browser.get("https://www.bumble.com")
        time.sleep(3)
        
        # Debug: Check current URL and page title
        print(f"{CYAN} Current URL: {browser.current_url}")
        print(f"{CYAN} Page title: {browser.title[:100] if browser.title else 'None'}")
        
        # Inject each cookie
        injected_count = 0
        failed_cookies = []
        for cookie in cookies:
            try:
                # Selenium requires 'sameSite' field, set it if missing
                if 'sameSite' not in cookie:
                    cookie['sameSite'] = 'None'
                elif cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    cookie['sameSite'] = 'None'
                
                # Remove 'expiry' if it's None or invalid (Selenium doesn't like None expiry)
                if 'expiry' in cookie and cookie['expiry'] is None:
                    del cookie['expiry']
                
                # Ensure domain starts with a dot for cross-subdomain cookies
                if 'domain' in cookie and not cookie['domain'].startswith('.'):
                    if '.' in cookie['domain']:
                        cookie['domain'] = f".{cookie['domain']}"
                
                browser.add_cookie(cookie)
                injected_count += 1
            except Exception as e:
                # Some cookies might fail (e.g., secure cookies on non-HTTPS, expired, etc.)
                if 'sameSite' not in str(e).lower():
                    failed_cookies.append((cookie.get('name', 'unknown'), str(e)))
        
        if failed_cookies:
            print(f"{YELLOW} Warning: Failed to inject {len(failed_cookies)} cookie(s):")
            for name, error in failed_cookies[:5]:  # Only show first 5 errors
                print(f"{YELLOW}   - {name}: {error[:100]}")
        
        print(f"{GREEN} Injected {injected_count} cookies")
        
        # Refresh page to apply cookies
        print(f"{CYAN} Refreshing page to apply cookies...")
        browser.refresh()
        time.sleep(3)
        
        # Check final URL
        final_url = browser.current_url
        print(f"{CYAN} Final URL after refresh: {final_url}")
        
        # Check if we're logged in (Bumble redirects to app.bumble.com or shows profile cards)
        if 'app.bumble.com' in final_url or 'bumble.com/app' in final_url:
            print(f"{GREEN} Successfully logged in via cookies!")
            return True
        elif 'login' in final_url.lower() or 'sign-in' in final_url.lower():
            print(f"{YELLOW} Warning: Still on login page - cookies may not be authentication cookies")
            print(f"{YELLOW} You need to be fully logged into Bumble in your browser first")
            return False
        else:
            # Wait a bit more and check for profile cards
            time.sleep(2)
            try:
                # Look for profile card elements
                profile_card = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-viewer, .encounters-card, [data-testid="encounters-card"]')
                if profile_card:
                    print(f"{GREEN} Profile cards detected - assuming logged in")
                    return True
            except:
                pass
            
            print(f"{YELLOW} Could not verify login status")
            return False
            
    except Exception as e:
        print(f"{RED} Error injecting cookies: {e}")
        import traceback
        traceback.print_exc()
        return False


def extract_profile_data(browser: webdriver.Chrome) -> Optional[Dict]:
    """
    Extract profile data from the current visible profile card.
    Returns None if no profile is visible.
    """
    try:
        # Wait for profile card to be visible
        wait = WebDriverWait(browser, 10)
        
        print(f"{CYAN} Attempting to extract profile data...")
        print(f"{CYAN} Current URL: {browser.current_url}")
        
        # Save current HTML for debugging
        try:
            with open('bumble_profile_debug.html', 'w', encoding='utf-8') as f:
                f.write(browser.page_source)
            print(f"{CYAN} Saved profile page HTML to bumble_profile_debug.html")
        except Exception:
            pass
        
        # Try multiple selectors for profile card - updated based on actual Bumble structure
        # Found: article.encounters-album contains the FIRST VISIBLE PROFILE with name/age
        #        article.encounters-story contains subsequent profile stories/cards
        profile_selectors = [
            'article.encounters-album',  # Primary - contains first visible profile with name/age
            'article[class*="encounters-album"]',
            'main article.encounters-album',
            'article.encounters-story',  # Fallback - contains profile stories
            'article[class*="encounters-story"]',
            'main article.encounters-story',
            'article',
        ]
        
        profile_element = None
        for selector in profile_selectors:
            try:
                elements = browser.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Find the first visible one
                    for elem in elements:
                        try:
                            if elem.is_displayed() and elem.text:
                                profile_element = elem
                                print(f"{GREEN} Found profile element using selector: {selector}")
                                print(f"{CYAN} Element tag: {profile_element.tag_name}")
                                print(f"{CYAN} Element classes: {profile_element.get_attribute('class')}")
                                break
                        except:
                            continue
                    if profile_element:
                        break
            except Exception as e:
                print(f"{YELLOW} Selector {selector} failed: {e}")
                continue
        
        if not profile_element:
            print(f"{YELLOW} No profile element found with any selector")
            # Try to find ANY visible article
            try:
                articles = browser.find_elements(By.TAG_NAME, 'article')
                for article in articles:
                    try:
                        if article.is_displayed() and article.text:
                            profile_element = article
                            print(f"{CYAN} Using first visible article element found")
                            break
                    except:
                        continue
            except Exception as e:
                print(f"{YELLOW} Fallback failed: {e}")
                return None
        
        if not profile_element:
            print(f"{YELLOW} Could not find any profile element")
            return None
        
        # Extract profile data
        profile_data = {
            "extracted_at": datetime.now().isoformat(),
        }
        
        # Extract name and age from article text (format: "Name, Age")
        # Bumble structure: article.encounters-story contains text like "Haley, 30"
        # Also check article.encounters-album which contains the first visible profile
        try:
            import re
            
            # Use the profile element we found (should be encounters-album for first profile)
            # If it's encounters-story, try to get the album element which contains the main profile info
            article_text = profile_element.text
            
            # If we're using encounters-story, try to find the album element for better extraction
            if 'encounters-story' in (profile_element.get_attribute('class') or ''):
                try:
                    album_elements = browser.find_elements(By.CSS_SELECTOR, 'article.encounters-album')
                    if album_elements and album_elements[0].is_displayed():
                        # Use album element for better name/age extraction
                        article_text = album_elements[0].text
                        print(f"{CYAN} Using encounters-album for name/age extraction")
                except:
                    pass
            
            # Try to find name/age pattern in text (e.g., "Jexe, 30" or "Haley, 30")
            # Pattern: Name (with possible newline) comma space Age
            # Handle format like "Jexe\n, 30" or "Haley, 30"
            
            # Try multiple patterns to handle different text formats
            name_age_patterns = [
                r'^([^\n,]+?)\s*,\s*(\d{2})\b',  # Start: "Name, 30" or "Name\n, 30"
                r'^([A-Z][^\n,]+?)\s*,\s*(\d{2})\b',  # Capitalized name: "Jexe, 30"
                r'([A-Z][a-zA-Z]+)\s*,\s*(\d{2})\b',  # Simple: "Name, 30"
            ]
            
            match = None
            for pattern in name_age_patterns:
                match = re.search(pattern, article_text, re.MULTILINE)
                if match:
                    name = match.group(1).strip()
                    # Remove newlines from name
                    name = re.sub(r'\s+', ' ', name).strip()
                    age = int(match.group(2))
                    # Validate: name should be reasonable length and age should be 18-99
                    if 2 <= len(name) <= 50 and 18 <= age <= 99:
                        profile_data["name"] = name
                        profile_data["age"] = age
                        print(f"{CYAN} Extracted name and age: {profile_data['name']}, {profile_data['age']}")
                        break
                    else:
                        match = None
            
            if not match:
                # Fallback: try to find name in section headings (e.g., "Haley's location" or "Jexe's location")
                try:
                    heading_pattern = r"([A-Z][a-zA-Z]+)'s\s+location"
                    match = re.search(heading_pattern, article_text, re.I)
                    if match:
                        name = match.group(1).strip()
                        if 2 <= len(name) <= 50:
                            profile_data["name"] = name
                            print(f"{CYAN} Extracted name from heading: {profile_data['name']}")
                except:
                    pass
        except Exception as e:
            print(f"{YELLOW} Error extracting name/age: {e}")
            profile_data["name"] = None
            profile_data["age"] = None
        
        # Age should already be extracted above, but add fallback if missing
        if "age" not in profile_data or profile_data["age"] is None:
            try:
                import re
                article_text = profile_element.text
                # Find two-digit number (likely age) in first 500 chars
                age_match = re.search(r'\b(\d{2})\b', article_text[:500])
                if age_match:
                    age = int(age_match.group(1))
                    if 18 <= age <= 99:  # Reasonable age range
                        profile_data["age"] = age
                        print(f"{CYAN} Extracted age (fallback): {age}")
            except Exception:
                profile_data["age"] = None
        
        # Extract bio/description - Bumble uses encounters-story-about__text
        try:
            bio_selectors = [
                '.encounters-story-about__text',  # Found in HTML
                '.encounters-story-section__content p',
                '.encounters-story-about',
                '[class*="story-about"]',
                '.encounters-story-viewer__bio',
                '.encounters-card__bio',
            ]
            bio_parts = []
            for selector in bio_selectors:
                try:
                    bio_elems = profile_element.find_elements(By.CSS_SELECTOR, selector)
                    for bio_elem in bio_elems:
                        bio_text = bio_elem.text.strip()
                        if bio_text and bio_text not in bio_parts:
                            bio_parts.append(bio_text)
                except NoSuchElementException:
                    continue
            if bio_parts:
                profile_data["bio"] = '\n'.join(bio_parts)
                print(f"{CYAN} Extracted bio: {len(bio_parts)} section(s)")
        except Exception as e:
            print(f"{YELLOW} Error extracting bio: {e}")
            profile_data["bio"] = None
        
        # Extract job/profession - look for "Senior Designer at Corporate Event Planning" pattern
        # Also check encounters-story-about badges which contain job info
        try:
            # First check article.encounters-album for main profile info
            album_text = None
            try:
                album_elem = browser.find_element(By.CSS_SELECTOR, 'article.encounters-album')
                album_text = album_elem.text
            except:
                pass
            
            search_text = album_text if album_text else profile_element.text
            
            # Look for job pattern: "Job Title at Company" or "Job Title"
            import re
            job_patterns = [
                r'([A-Z][^,\n]*(?:Designer|Engineer|Manager|Developer|Director|Specialist|Analyst|Coordinator|Consultant|Executive|Officer)[^,\n]*(?:at\s+[A-Z][^,\n]+)?)',
                r'([A-Z][^,\n]*at\s+[A-Z][^,\n]+)',
            ]
            
            for pattern in job_patterns:
                match = re.search(pattern, search_text)
                if match:
                    job_text = match.group(1).strip()
                    # Clean up (remove trailing periods, etc.)
                    job_text = re.sub(r'\.$', '', job_text).strip()
                    if len(job_text) > 3:  # Minimum reasonable job title length
                        profile_data["job"] = job_text
                        print(f"{CYAN} Extracted job: {profile_data['job']}")
                        break
        except Exception as e:
            print(f"{YELLOW} Error extracting job: {e}")
            profile_data["job"] = None
        
        # Extract education - look for badges with "Undergraduate degree" or university names
        # Also check encounters-story-about badges
        try:
            import re
            # Check badges/pills for education
            badge_selectors = [
                '.encounters-story-about__badge',
                '.pill[data-qa-role="pill"]',
                '[class*="badge"]',
            ]
            
            education_texts = []
            for selector in badge_selectors:
                try:
                    badges = profile_element.find_elements(By.CSS_SELECTOR, selector)
                    for badge in badges:
                        badge_text = badge.text.strip()
                        # Check if badge contains education keywords
                        if any(keyword in badge_text.lower() for keyword in ['degree', 'university', 'college', 'school', 'undergraduate', 'graduate', 'bachelor', 'master', 'doctorate']):
                            education_texts.append(badge_text)
                except:
                    continue
            
            # Also search article text for university patterns
            article_text = profile_element.text
            university_pattern = r'([A-Z][^,\n]*(?:University|College|School|Institute|State University|Tech)[^,\n]*)'
            uni_matches = re.findall(university_pattern, article_text)
            if uni_matches:
                education_texts.extend(uni_matches)
            
            if education_texts:
                # Get first unique education entry
                profile_data["education"] = education_texts[0].strip()
                print(f"{CYAN} Extracted education: {profile_data['education']}")
        except Exception as e:
            print(f"{YELLOW} Error extracting education: {e}")
            profile_data["education"] = None
        
        # Extract image URLs - Bumble uses media-box__picture-image
        try:
            image_selectors = [
                '.media-box__picture-image',  # Found in HTML
                'article.encounters-album img',
                'article.encounters-story img',
                '.encounters-story__content img',
                'picture img',
                'img[class*="media-box"]',
            ]
            image_urls = []
            seen_urls = set()
            
            # First try to get images from the album (main profile images)
            try:
                album_elem = browser.find_element(By.CSS_SELECTOR, 'article.encounters-album')
                images = album_elem.find_elements(By.TAG_NAME, 'img')
                for img in images:
                    src = img.get_attribute('src') or img.get_attribute('data-src')
                    if src and src not in seen_urls:
                        # Filter out placeholders, icons, and small images
                        if 'placeholder' not in src.lower() and 'icon' not in src.lower() and len(src) > 50:
                            # Bumble images are often in format like "//us1.ecdn2.bumbcdn.com/p519/..."
                            if 'bumbcdn.com' in src or 'bumble.com' in src:
                                image_urls.append(src)
                                seen_urls.add(src)
            except:
                pass
            
            # Fallback: try other selectors
            for selector in image_selectors:
                try:
                    images = browser.find_elements(By.CSS_SELECTOR, selector)
                    for img in images:
                        src = img.get_attribute('src') or img.get_attribute('data-src')
                        if src and src not in seen_urls:
                            if 'placeholder' not in src.lower() and 'icon' not in src.lower() and len(src) > 50:
                                if 'bumbcdn.com' in src or 'bumble.com' in src:
                                    image_urls.append(src)
                                    seen_urls.add(src)
                except:
                    continue
            
            profile_data["image_urls"] = list(set(image_urls))  # Remove duplicates
            if image_urls:
                print(f"{CYAN} Extracted {len(image_urls)} image(s)")
        except Exception as e:
            print(f"{YELLOW} Error extracting images: {e}")
            profile_data["image_urls"] = []
        
        # Extract location/distance - Bumble uses location-widget
        try:
            location_selectors = [
                '.location-widget__town',  # Found in HTML: "Denver"
                '.location-widget__distance',  # Found in HTML: "~3 miles away"
                '.encounters-story-section--location',
                '[class*="location-widget"]',
                '.encounters-story-section__content[class*="location"]',
            ]
            
            location_parts = []
            
            # Try to find location widget
            for selector in location_selectors:
                try:
                    loc_elems = browser.find_elements(By.CSS_SELECTOR, selector)
                    for loc_elem in loc_elems:
                        loc_text = loc_elem.text.strip()
                        if loc_text and loc_text not in location_parts:
                            location_parts.append(loc_text)
                except:
                    continue
            
            if location_parts:
                profile_data["location"] = ' | '.join(location_parts)
                print(f"{CYAN} Extracted location: {profile_data['location']}")
            else:
                # Fallback: search for location patterns in text
                import re
                article_text = profile_element.text
                # Look for "miles away" or city patterns
                location_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*~?\s*(\d+)\s*miles?\s*away'
                match = re.search(location_pattern, article_text, re.I)
                if match:
                    profile_data["location"] = f"{match.group(1)} | {match.group(2)} miles away"
        except Exception as e:
            print(f"{YELLOW} Error extracting location: {e}")
            profile_data["location"] = None
        
        # Extract preferences (looking for) - from badges/pills
        try:
            # Look for badges with preferences like "Relationship", "Something casual", etc.
            badge_selectors = [
                '.encounters-story-about__badge',
                '.pill[data-qa-role="pill"]',
                '[class*="badge"][class*="intentions"]',  # Intentions badge
            ]
            
            preference_keywords = ['relationship', 'something casual', 'don\'t know yet', 'friendship', 'network']
            preferences = []
            
            for selector in badge_selectors:
                try:
                    badges = profile_element.find_elements(By.CSS_SELECTOR, selector)
                    for badge in badges:
                        badge_text = badge.text.strip()
                        if any(keyword in badge_text.lower() for keyword in preference_keywords):
                            preferences.append(badge_text)
                except:
                    continue
            
            if preferences:
                profile_data["preferences"] = ' | '.join(preferences)
                print(f"{CYAN} Extracted preferences: {profile_data['preferences']}")
        except Exception as e:
            print(f"{YELLOW} Error extracting preferences: {e}")
            profile_data["preferences"] = None
        
        # Extract job/profession from bio text (usually first line after name/age)
        if not profile_data.get("job") and profile_data.get("bio"):
            try:
                bio_lines = profile_data["bio"].split('\n')
                if bio_lines:
                    # First non-empty line might be job
                    first_line = bio_lines[0].strip()
                    # Check if it looks like a job (contains "at", "Designer", "Engineer", etc.)
                    job_keywords = ['at ', 'designer', 'engineer', 'manager', 'developer', 'director', 'specialist', 'analyst']
                    if any(keyword in first_line.lower() for keyword in job_keywords):
                        profile_data["job"] = first_line
                        print(f"{CYAN} Extracted job: {profile_data['job']}")
            except Exception:
                pass
        
        # Extract education (usually contains "University", "College", "School")
        if not profile_data.get("education") and profile_data.get("bio"):
            try:
                import re
                education_pattern = r'([A-Z][^,\n]*(?:University|College|School|Institute)[^,\n]*)'
                matches = re.findall(education_pattern, profile_data["bio"])
                if matches:
                    profile_data["education"] = matches[0].strip()
                    print(f"{CYAN} Extracted education: {profile_data['education']}")
            except Exception:
                pass
        
        # If we still don't have a name, try extracting from entire article text
        if not profile_data.get("name"):
            try:
                import re
                article_text = profile_element.text
                # Try simple pattern: first word before comma
                name_pattern = r'^([^,\n]+),'
                match = re.search(name_pattern, article_text)
                if match:
                    profile_data["name"] = match.group(1).strip()
                    print(f"{CYAN} Extracted name from fallback: {profile_data['name']}")
            except Exception:
                pass
        
        # Print extracted data summary
        if profile_data.get("name"):
            print(f"{GREEN} Profile extracted: {profile_data.get('name', 'Unknown')} ({profile_data.get('age', '?')})")
        else:
            print(f"{YELLOW} Warning: Could not extract name from profile")
        
        return profile_data
        
    except TimeoutException:
        print(f"{YELLOW} Warning: Profile card not found or not visible")
        return None
    except Exception as e:
        print(f"{YELLOW} Warning: Error extracting profile data: {e}")
        return None


def swipe_right(browser: webdriver.Chrome) -> bool:
    """
    Swipe right (like) on the current profile.
    Returns True if swipe was successful, False otherwise.
    """
    try:
        # Selector for the like button - found in actual HTML:
        # <div class="encounters-action tooltip-activator encounters-action--like" 
        #      role="button" data-qa-role="encounters-action-like" aria-label="Like">
        like_button_selector = '.encounters-action.encounters-action--like[data-qa-role="encounters-action-like"]'
        
        # Also try alternative selectors
        alternative_selectors = [
            '[data-qa-role="encounters-action-like"]',  # Found in HTML
            '.encounters-action--like[role="button"]',
            '.encounters-action--like',
            '[aria-label="Like"]',
            '[aria-label*="Like"]',
            '[data-testid="like-button"]',
            'button[aria-label*="Like"]',
        ]
        
        wait = WebDriverWait(browser, 5)
        
        # Try primary selector first
        try:
            like_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, like_button_selector)))
            like_button.click()
            print(f"{GREEN} Swiped right (like button clicked)")
            return True
        except TimeoutException:
            pass
        
        # Try alternative selectors
        for selector in alternative_selectors:
            try:
                like_button = browser.find_element(By.CSS_SELECTOR, selector)
                if like_button.is_displayed() and like_button.is_enabled():
                    like_button.click()
                    print(f"{GREEN} Swiped right (alternative selector: {selector})")
                    return True
            except (NoSuchElementException, ElementNotInteractableException):
                continue
        
        # Try JavaScript click as fallback - use the correct selector from HTML
        try:
            result = browser.execute_script("""
                // Try multiple selectors based on actual Bumble HTML structure
                const selectors = [
                    '[data-qa-role="encounters-action-like"]',
                    '.encounters-action--like[role="button"]',
                    '.encounters-action.encounters-action--like',
                    '[aria-label="Like"]'
                ];
                
                for (const selector of selectors) {
                    const likeButton = document.querySelector(selector);
                    if (likeButton && likeButton.offsetParent !== null) {
                        likeButton.click();
                        return true;
                    }
                }
                return false;
            """)
            if result:
                print(f"{GREEN} Swiped right (JavaScript click)")
                return True
        except Exception as e:
            print(f"{YELLOW} JavaScript click failed: {e}")
            pass
        
        print(f"{YELLOW} Warning: Could not find or click like button")
        return False
        
    except Exception as e:
        print(f"{YELLOW} Warning: Error swiping right: {e}")
        return False


def handle_match_popup(browser: webdriver.Chrome) -> bool:
    """
    Handle match popup or continue button after a match.
    Returns True if handled, False otherwise.
    """
    try:
        # Selector for continue button (from original bumbleAutoLiker.js)
        continue_button_selector = "#main > div > div.page__layout > main > div.page__content-inner > article > div > footer > div.encounters-match__cta > div:nth-child(2) > button"
        
        alternative_selectors = [
            'button[data-testid="continue-button"]',
            'button:contains("Continue")',
            '.encounters-match__cta button',
            'button.continue-button',
        ]
        
        # Try primary selector
        try:
            continue_button = browser.find_element(By.CSS_SELECTOR, continue_button_selector)
            if continue_button.is_displayed() and continue_button.is_enabled():
                continue_button.click()
                print(f"{CYAN} Clicked continue button (match popup)")
                time.sleep(1)
                return True
        except NoSuchElementException:
            pass
        
        # Try alternative selectors
        for selector in alternative_selectors:
            try:
                if ':contains(' in selector:
                    # Use JavaScript for :contains pseudo-selector
                    browser.execute_script(f"""
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const continueBtn = buttons.find(btn => btn.textContent.includes('Continue') || btn.textContent.includes('continue'));
                        if (continueBtn) {{
                            continueBtn.click();
                            return true;
                        }}
                        return false;
                    """)
                    print(f"{CYAN} Clicked continue button (JavaScript)")
                    time.sleep(1)
                    return True
                else:
                    continue_button = browser.find_element(By.CSS_SELECTOR, selector)
                    if continue_button.is_displayed() and continue_button.is_enabled():
                        continue_button.click()
                        print(f"{CYAN} Clicked continue button (alternative selector)")
                        time.sleep(1)
                        return True
            except (NoSuchElementException, ElementNotInteractableException):
                continue
        
        return False
        
    except Exception as e:
        # Match popup is optional, don't fail if it doesn't exist
        return False


def set_location_geolocation(browser: webdriver.Chrome, location: str) -> bool:
    """
    Set location using browser geolocation API (alternative method).
    Uses geocoding to get coordinates for the location, then sets browser geolocation.
    
    Args:
        browser: Selenium WebDriver instance
        location: Location string (e.g., "Seattle" or "Seattle, WA")
    
    Returns:
        True if geolocation was set successfully, False otherwise
    """
    try:
        print(f"{CYAN} Attempting to set location via geolocation API: {location}")
        
        # Common coordinates for major cities (fallback if geocoding fails)
        city_coordinates = {
            'seattle': {'latitude': 47.6062, 'longitude': -122.3321},
            'seattle, wa': {'latitude': 47.6062, 'longitude': -122.3321},
            'seattle, washington': {'latitude': 47.6062, 'longitude': -122.3321},
            'new york': {'latitude': 40.7128, 'longitude': -74.0060},
            'new york, ny': {'latitude': 40.7128, 'longitude': -74.0060},
            'los angeles': {'latitude': 34.0522, 'longitude': -118.2437},
            'los angeles, ca': {'latitude': 34.0522, 'longitude': -118.2437},
            'chicago': {'latitude': 41.8781, 'longitude': -87.6298},
            'chicago, il': {'latitude': 41.8781, 'longitude': -87.6298},
            'san francisco': {'latitude': 37.7749, 'longitude': -122.4194},
            'san francisco, ca': {'latitude': 37.7749, 'longitude': -122.4194},
            'denver': {'latitude': 39.7392, 'longitude': -104.9903},
            'denver, co': {'latitude': 39.7392, 'longitude': -104.9903},
            'austin': {'latitude': 30.2672, 'longitude': -97.7431},
            'austin, tx': {'latitude': 30.2672, 'longitude': -97.7431},
            'miami': {'latitude': 25.7617, 'longitude': -80.1918},
            'miami, fl': {'latitude': 25.7617, 'longitude': -80.1918},
        }
        
        location_lower = location.lower().strip()
        coords = city_coordinates.get(location_lower)
        
        if not coords:
            # Try to extract city name (remove state/country)
            city_name = location.split(',')[0].strip().lower()
            coords = city_coordinates.get(city_name)
            
            if not coords:
                print(f"{YELLOW} Location '{location}' not in predefined list.")
                print(f"{YELLOW} Supported cities: Seattle, New York, Los Angeles, Chicago, San Francisco, Denver, Austin, Miami")
                print(f"{YELLOW} Using Seattle coordinates as fallback. For other cities, add coordinates to city_coordinates dict.")
                coords = {'latitude': 47.6062, 'longitude': -122.3321}
        
        # Set geolocation using Chrome DevTools Protocol
        print(f"{CYAN} Setting geolocation to: {coords['latitude']}, {coords['longitude']}")
        browser.execute_cdp_cmd('Emulation.setGeolocationOverride', {
            'latitude': coords['latitude'],
            'longitude': coords['longitude'],
            'accuracy': 100
        })
        
        print(f"{GREEN} Geolocation set successfully")
        return True
        
    except Exception as e:
        print(f"{YELLOW} Error setting geolocation: {e}")
        return False


def set_location(browser: webdriver.Chrome, location: str) -> bool:
    """
    Set location filter in Bumble by navigating to settings and updating location.
    Tries multiple methods: settings UI, filters UI, and browser geolocation API.
    
    Args:
        browser: Selenium WebDriver instance
        location: Location string (e.g., "Seattle" or "Seattle, WA")
    
    Returns:
        True if location was set successfully, False otherwise
    """
    try:
        print(f"{CYAN} Setting location to: {location}")
        
        # First, try setting via geolocation API (most reliable)
        if set_location_geolocation(browser, location):
            print(f"{CYAN} Location set via geolocation API, refreshing page...")
            browser.refresh()
            time.sleep(3)
            return True
        
        # Navigate to settings page
        # Bumble settings are typically at /app/settings or accessible via a settings button
        print(f"{CYAN} Navigating to Bumble settings...")
        
        # Try multiple ways to access settings:
        # 1. Direct URL
        settings_urls = [
            "https://www.bumble.com/app/settings",
            "https://app.bumble.com/settings",
            "https://www.bumble.com/app/preferences",
        ]
        
        settings_accessed = False
        for url in settings_urls:
            try:
                browser.get(url)
                time.sleep(3)
                if 'settings' in browser.current_url.lower() or 'preferences' in browser.current_url.lower():
                    print(f"{GREEN} Accessed settings page: {browser.current_url}")
                    settings_accessed = True
                    break
            except:
                continue
        
        if not settings_accessed:
            # Try to find settings button on main page
            print(f"{CYAN} Trying to find settings button on main page...")
            try:
                # Look for settings/gear icon button
                settings_selectors = [
                    'button[aria-label*="Settings"]',
                    'button[aria-label*="settings"]',
                    'a[href*="settings"]',
                    'button[class*="settings"]',
                    '[data-testid*="settings"]',
                    'svg[class*="settings"]',
                    '.settings-button',
                ]
                
                for selector in settings_selectors:
                    try:
                        settings_btn = browser.find_element(By.CSS_SELECTOR, selector)
                        if settings_btn.is_displayed():
                            settings_btn.click()
                            time.sleep(3)
                            settings_accessed = True
                            print(f"{GREEN} Clicked settings button")
                            break
                    except:
                        continue
            except:
                pass
        
        if not settings_accessed:
            print(f"{YELLOW} Could not access settings page, trying to set location via filters...")
            # Try to access filters directly
            try:
                # Look for filter button
                filter_selectors = [
                    'button[aria-label*="Filter"]',
                    'button[aria-label*="filter"]',
                    'button[class*="filter"]',
                    '[data-testid*="filter"]',
                ]
                
                for selector in filter_selectors:
                    try:
                        filter_btn = browser.find_element(By.CSS_SELECTOR, selector)
                        if filter_btn.is_displayed():
                            filter_btn.click()
                            time.sleep(2)
                            print(f"{GREEN} Opened filters")
                            break
                    except:
                        continue
            except:
                pass
        
        # Try to find location input/selector
        print(f"{CYAN} Looking for location input field...")
        location_selectors = [
            'input[placeholder*="location" i]',
            'input[placeholder*="city" i]',
            'input[name*="location" i]',
            'input[id*="location" i]',
            'input[type="text"][class*="location"]',
            'select[name*="location" i]',
            'select[id*="location" i]',
        ]
        
        location_set = False
        for selector in location_selectors:
            try:
                location_input = browser.find_element(By.CSS_SELECTOR, selector)
                if location_input.is_displayed():
                    print(f"{GREEN} Found location input: {selector}")
                    # Clear and set location
                    location_input.clear()
                    location_input.send_keys(location)
                    time.sleep(1)
                    
                    # Try to submit or select from dropdown
                    location_input.send_keys(Keys.RETURN)
                    time.sleep(2)
                    
                    # Look for save/apply button
                    save_selectors = [
                        'button[type="submit"]',
                        'button[class*="save"]',
                        'button[class*="apply"]',
                        'button[aria-label*="Save" i]',
                        'button[aria-label*="Apply" i]',
                    ]
                    
                    for save_selector in save_selectors:
                        try:
                            save_btn = browser.find_element(By.CSS_SELECTOR, save_selector)
                            if save_btn.is_displayed():
                                save_btn.click()
                                time.sleep(2)
                                print(f"{GREEN} Clicked save/apply button")
                                break
                        except:
                            continue
                    
                    location_set = True
                    break
            except:
                continue
        
        if location_set:
            print(f"{GREEN} Location set to: {location}")
            # Navigate back to app page
            browser.get("https://www.bumble.com/app")
            time.sleep(3)
            return True
        else:
            print(f"{YELLOW} Could not find location input field. Location may need to be set manually in Bumble settings.")
            print(f"{YELLOW} Note: Bumble may use browser geolocation or require manual location setting.")
            # Navigate back to app page
            browser.get("https://www.bumble.com/app")
            time.sleep(3)
            return False
            
    except Exception as e:
        print(f"{YELLOW} Error setting location: {e}")
        # Navigate back to app page
        try:
            browser.get("https://www.bumble.com/app")
            time.sleep(3)
        except:
            pass
        return False


def scrape_profiles(cookie_file: str = None, limit: int = None, delay: float = 1.5,
                    output_format: str = 'json', output_file: str = None, headless: bool = True,
                    location: str = None):
    """
    Scrape Bumble profiles by extracting data before swiping right.
    
    Args:
        cookie_file: Path to cookie file extracted by extract_bumble_cookies.py (recommended)
        limit: Maximum number of profiles to extract/swipe (default: unlimited)
        delay: Delay between swipes in seconds (default: 1.5, recommended: 1-3 to avoid detection)
        output_format: Output format ('json' or 'csv')
        output_file: Output file path (optional, auto-generated if not provided)
        headless: Run browser in headless mode (default: True - recommended for automation)
        location: Location to set (e.g., "Seattle" or "Seattle, WA") - optional
    """
    browser = None
    try:
        print(f"{CYAN} Initializing Bumble scraper...")
        print(f"{CYAN} Mode: Extract profile data BEFORE swiping right")
        print(f"{CYAN} Headless: {headless}")
        
        def create_chrome_options():
            """Create a new ChromeOptions object (cannot be reused)"""
            options = uc.ChromeOptions()
            if headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            return options
        
        # Create undetected Chrome driver (undetected-chromedriver handles anti-detection automatically)
        # Let undetected-chromedriver auto-detect and download the correct ChromeDriver version
        print(f"{CYAN} Starting browser...")
        print(f"{CYAN} Auto-detecting Chrome version and downloading compatible ChromeDriver...")
        
        # Try to detect Chrome version first to ensure we get the right ChromeDriver
        chrome_version = None
        try:
            import subprocess
            if sys.platform == 'win32':
                # Windows: Check registry for Chrome version
                try:
                    result = subprocess.run(
                        ['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        match = re.search(r'version\s+REG_SZ\s+(\d+)', result.stdout)
                        if match:
                            chrome_version = int(match.group(1))
                            print(f"{CYAN} Detected Chrome version: {chrome_version}")
                except Exception as e:
                    print(f"{YELLOW} Could not detect Chrome version from registry: {e}")
                    # Try alternative method: check Chrome executable
                    try:
                        chrome_paths = [
                            os.path.expanduser('~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe'),
                            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
                            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
                        ]
                        for chrome_path in chrome_paths:
                            if os.path.exists(chrome_path):
                                result = subprocess.run(
                                    [chrome_path, '--version'],
                                    capture_output=True, text=True, timeout=5
                                )
                                if result.returncode == 0:
                                    match = re.search(r'(\d+)\.', result.stdout)
                                    if match:
                                        chrome_version = int(match.group(1))
                                        print(f"{CYAN} Detected Chrome version from executable: {chrome_version}")
                                        break
                    except:
                        pass
        except Exception as e:
            print(f"{YELLOW} Could not detect Chrome version: {e}")
        
        # Try to initialize browser with detected version or auto-detection
        browser = None
        try:
            if chrome_version:
                print(f"{CYAN} Using detected Chrome version: {chrome_version}")
                options = create_chrome_options()
                browser = uc.Chrome(options=options, version_main=chrome_version, headless=headless, use_subprocess=True)
            else:
                print(f"{CYAN} Using auto-detection for Chrome version...")
                options = create_chrome_options()
                browser = uc.Chrome(options=options, version_main=None, headless=headless, use_subprocess=True)
        except Exception as e:
            error_msg = str(e)
            print(f"{YELLOW} Initial browser initialization failed: {error_msg[:300]}")
            
            # If version mismatch error, try to extract version from error and retry
            if 'Chrome version' in error_msg or 'ChromeDriver only supports' in error_msg:
                print(f"{CYAN} Attempting to fix ChromeDriver version mismatch...")
                # Extract the actual Chrome version from the error message
                match = re.search(r'Current browser version is (\d+)\.', error_msg)
                if match:
                    actual_chrome_version = int(match.group(1))
                    print(f"{CYAN} Detected actual Chrome version from error: {actual_chrome_version}")
                    if actual_chrome_version != chrome_version:
                        chrome_version = actual_chrome_version
                        print(f"{CYAN} Retrying with correct Chrome version: {chrome_version}")
                        options = create_chrome_options()
                        browser = uc.Chrome(options=options, version_main=chrome_version, headless=headless, use_subprocess=True)
                    else:
                        raise
                else:
                    raise
            else:
                raise
        browser.maximize_window()
        
        # Execute script to hide webdriver property
        browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            '''
        })
        
        # Try cookie-based authentication first (recommended)
        logged_in = False
        if cookie_file:
            print(f"{CYAN} Attempting cookie-based authentication...")
            cookies = load_cookies_from_file(cookie_file)
            if cookies:
                logged_in = inject_cookies_to_browser(browser, cookies)
                if logged_in:
                    print(f"{GREEN} Authentication successful via cookies")
        
        # Navigate to Bumble if not already logged in
        if not logged_in:
            print(f"{CYAN} Navigating to Bumble...")
            browser.get("https://www.bumble.com")
            time.sleep(5)
            
            # Check if we're on login page
            if 'login' in browser.current_url.lower() or 'sign-in' in browser.current_url.lower():
                print(f"{RED} Error: Not logged in and no authentication method provided")
                print(f"{YELLOW} Please provide --cookies <file> (recommended) - Extract cookies automatically with --auto-session")
                print(f"{YELLOW} Or manually log in to Bumble in your browser first, then extract cookies")
                sys.exit(1)
        
        # Wait for first profile to load
        print(f"{CYAN} Waiting for profile cards to load...")
        print(f"{CYAN} Current URL: {browser.current_url}")
        print(f"{CYAN} Page title: {browser.title}")
        
        # Navigate to the app (encounters) page if needed
        if 'app.bumble.com/app' not in browser.current_url and '/app' not in browser.current_url:
            # Try to navigate to the encounters page
            print(f"{CYAN} Navigating to encounters page...")
            try:
                browser.get("https://www.bumble.com/app")
                time.sleep(5)
                print(f"{CYAN} URL after navigation: {browser.current_url}")
                print(f"{CYAN} Page title: {browser.title}")
            except Exception as e:
                print(f"{YELLOW} Error navigating: {e}")
        
        # Set location if provided
        if location:
            set_location(browser, location)
            # Wait a bit after setting location
            time.sleep(3)
        
        # Save HTML for debugging (first time)
        try:
            with open('bumble_page_debug.html', 'w', encoding='utf-8') as f:
                f.write(browser.page_source)
            print(f"{CYAN} Saved page HTML to bumble_page_debug.html for inspection")
        except Exception as e:
            print(f"{YELLOW} Could not save HTML: {e}")
        
        # Wait a bit more for profile to load
        time.sleep(3)
        
        # Check what elements are visible
        print(f"{CYAN} Inspecting page structure...")
        try:
            # Try to find any profile-related elements
            all_buttons = browser.find_elements(By.TAG_NAME, 'button')
            print(f"{CYAN} Found {len(all_buttons)} button elements on page")
            
            # Look for common profile card selectors
            test_selectors = [
                '.encounters-story-viewer',
                '.encounters-card',
                '[data-testid*="encounters"]',
                '[data-testid*="profile"]',
                '[data-testid*="card"]',
                '.encounters',
                '.profile-card',
                'article',
                'main',
            ]
            
            for selector in test_selectors:
                try:
                    elements = browser.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"{CYAN} Found {len(elements)} element(s) with selector: {selector}")
                        for i, elem in enumerate(elements[:3]):  # Show first 3
                            try:
                                text = elem.text[:100] if elem.text else "No text"
                                tag = elem.tag_name
                                classes = elem.get_attribute('class')[:50] if elem.get_attribute('class') else "No class"
                                print(f"{CYAN}   [{i}] {tag} | class={classes} | text={text}...")
                            except:
                                pass
                except Exception:
                    pass
        except Exception as e:
            print(f"{YELLOW} Error inspecting page: {e}")
        
        # Scrape profiles
        all_profiles = []
        profile_count = 0
        
        while True:
            # Check limit
            if limit and profile_count >= limit:
                print(f"{CYAN} Reached limit of {limit} profiles")
                break
            
            print(f"{CYAN} Profile {profile_count + 1}: Extracting data...")
            
            # Extract profile data BEFORE swiping
            profile_data = extract_profile_data(browser)
            
            if not profile_data:
                print(f"{YELLOW} Warning: Could not extract profile data - no profile visible")
                
                # Check if we hit the end (no more profiles)
                page_source = browser.page_source.lower()
                if 'no more profiles' in page_source or 'out of people' in page_source or 'no one new' in page_source:
                    print(f"{CYAN} No more profiles available")
                    break
                
                # Try handling match popup or continue button
                if handle_match_popup(browser):
                    time.sleep(2)
                    continue
                
                # Wait a bit and try again
                time.sleep(2)
                continue
            
            # Add profile data
            if profile_data.get("name"):
                all_profiles.append(profile_data)
                profile_count += 1
                print(f"{GREEN} Extracted: {profile_data.get('name', 'Unknown')} ({profile_data.get('age', '?')})")
            else:
                print(f"{YELLOW} Warning: Profile data incomplete (missing name)")
                # Still save it, but mark as incomplete
                profile_data["_incomplete"] = True
                all_profiles.append(profile_data)
                profile_count += 1
            
            # NOW swipe right after extraction
            print(f"{CYAN} Swiping right on profile {profile_count}...")
            swipe_success = swipe_right(browser)
            
            if not swipe_success:
                print(f"{YELLOW} Warning: Swipe failed - profile may have already been swiped")
            
            # Wait for next profile to load
            time.sleep(delay)
            
            # Add random delay variation (0-1 second) to appear more human-like
            if delay > 0:
                random_delay = random.uniform(0, min(1.0, delay * 0.5))
                time.sleep(random_delay)
            
            # Handle match popup if it appears
            handle_match_popup(browser)
            
            # Wait a bit more for new profile to load
            time.sleep(1)
        
        # Save all profiles
        if not all_profiles:
            print(f"{RED} Error: No profiles extracted")
            sys.exit(1)
        
        print(f"{GREEN} Successfully extracted {len(all_profiles)} profile(s)")
        
        # Generate output filename if not provided
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"bumble_profiles_{timestamp}.{output_format}"
        
        # Save to file
        if output_format == 'json':
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_profiles, f, indent=2, ensure_ascii=False)
        else:  # CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                if all_profiles:
                    fieldnames = ['extracted_at', 'name', 'age', 'bio', 'job', 'education', 'location', 'preferences', 'image_urls']
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                    writer.writeheader()
                    for profile in all_profiles:
                        # Convert image_urls list to semicolon-separated string for CSV
                        row = profile.copy()
                        if 'image_urls' in row and isinstance(row['image_urls'], list):
                            row['image_urls'] = '; '.join(row['image_urls'])
                        writer.writerow(row)
        
        print(f"{GREEN} Data saved to: {output_file}")
        print(f"{CYAN} Summary: {len(all_profiles)} profile(s) extracted and swiped right")
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW} Interrupted by user")
        if all_profiles:
            print(f"{CYAN} Saving {len(all_profiles)} profile(s) extracted so far...")
            if not output_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f"bumble_profiles_{timestamp}_partial.{output_format}"
            if output_format == 'json':
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_profiles, f, indent=2, ensure_ascii=False)
            else:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    if all_profiles:
                        fieldnames = ['extracted_at', 'name', 'age', 'bio', 'job', 'education', 'location', 'preferences', 'image_urls']
                        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                        writer.writeheader()
                        for profile in all_profiles:
                            row = profile.copy()
                            if 'image_urls' in row and isinstance(row['image_urls'], list):
                                row['image_urls'] = '; '.join(row['image_urls'])
                            writer.writerow(row)
            print(f"{GREEN} Partial data saved to: {output_file}")
    except Exception as e:
        print(f"{RED} Error scraping profiles: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if browser:
            print(f"{CYAN} Closing browser...")
            browser.quit()


def main():
    parser = argparse.ArgumentParser(description='Bumble Profile Scraper - Extract profile data and swipe right automatically')
    parser.add_argument('--cookies', '--cookie-file', dest='cookie_file',
                        help='Path to cookie file extracted by extract_bumble_cookies.py (recommended)')
    parser.add_argument('--limit', type=int,
                        help='Maximum number of profiles to extract/swipe (default: unlimited)')
    parser.add_argument('--delay', type=float, default=1.5,
                        help='Delay between swipes in seconds (default: 1.5, recommended: 1-3 to avoid detection)')
    parser.add_argument('--format', choices=['json', 'csv'], default='json',
                        help='Output format (default: json)')
    parser.add_argument('--output', '-o',
                        help='Output file path (optional, auto-generated if not provided)')
    parser.add_argument('--headless', action='store_true', default=None,
                        help='Run in headless mode (default: True for automation)')
    parser.add_argument('--no-headless', dest='headless', action='store_false',
                        help='Disable headless mode (show browser window for debugging)')
    parser.add_argument('--location', type=str, default=None,
                        help='Set location filter (e.g., "Seattle" or "Seattle, WA")')
    
    args = parser.parse_args()
    
    # Default to headless=True unless explicitly disabled
    # If neither flag is provided, default to headless mode
    if args.headless is None:
        args.headless = True  # Default to headless for automation
    
    scrape_profiles(
        cookie_file=args.cookie_file,
        limit=args.limit,
        delay=args.delay,
        output_format=args.format,
        output_file=args.output,
        headless=args.headless,
        location=args.location
    )


if __name__ == '__main__':
    main()


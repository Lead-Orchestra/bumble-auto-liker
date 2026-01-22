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
import subprocess
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

# Safe print function that handles Unicode encoding errors
def safe_print(*args, **kwargs):
    """Print function that safely handles Unicode characters on Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback: encode to ASCII with error handling
        encoded_args = []
        for arg in args:
            if isinstance(arg, str):
                try:
                    encoded_args.append(arg.encode('ascii', 'replace').decode('ascii'))
                except:
                    encoded_args.append(repr(arg))
            else:
                encoded_args.append(str(arg))
        print(*encoded_args, **kwargs)


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


def extract_profile_data(browser: webdriver.Chrome, gender: str = None) -> Optional[Dict]:
    """
    Extract profile data from the current visible profile card.
    Returns None if no profile is visible.
    
    Args:
        browser: Selenium WebDriver instance
        gender: Optional gender to set for the profile (e.g., "female", "male", "non-binary")
    """
    try:
        # Wait for profile card to be visible
        wait = WebDriverWait(browser, 10)
        
        print(f"{CYAN} Attempting to extract profile data...")
        print(f"{CYAN} Current URL: {browser.current_url}")
        
        # Wait for initial profile to load
        print(f"{CYAN} Waiting for profile to load...")
        time.sleep(2)
        
        # Based on HTML structure, all profile data is already in the DOM
        # The encounters-album contains all story sections (About, Questions, Location, etc.)
        # We don't need to scroll - just wait for the DOM to be fully loaded
        try:
            print(f"{CYAN} Checking if all profile sections are in DOM...")
            
            # Wait a bit more for any lazy-loaded content
            time.sleep(2)
            
            # Verify key sections are present in DOM (they should all be there)
            try:
                about_section = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-section--about')
                question_sections = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-section--question')
                location_section = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-section--location')
                badges = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-about__badge')
                
                print(f"{CYAN} Found sections in DOM: About={len(about_section)}, Questions={len(question_sections)}, Location={len(location_section)}, Badges={len(badges)}")
                
                # If sections are missing, wait a bit more (they might be loading)
                if len(about_section) == 0 and len(question_sections) == 0:
                    print(f"{YELLOW} Sections not found yet, waiting a bit more...")
                    time.sleep(2)
            except Exception as e:
                print(f"{YELLOW} Error checking sections: {e}")
                
        except Exception as e:
            print(f"{YELLOW} Error during section check: {e}")
        
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
        
        # Set gender if provided via command line argument
        if gender:
            profile_data["gender"] = gender
        
        # Extract name and age from specific selectors (more reliable than regex)
        # HTML structure: .encounters-story-profile__name and .encounters-story-profile__age
        try:
            # Try direct selectors first (most reliable)
            name_selectors = [
                '.encounters-story-profile__name',  # Found in HTML: <span class="encounters-story-profile__name">Kristine</span>
                '.encounters-story-profile__user .encounters-story-profile__name',
                'article.encounters-album .encounters-story-profile__name',
            ]
            
            age_selectors = [
                '.encounters-story-profile__age',  # Found in HTML: <span class="encounters-story-profile__age">, 28</span>
                '.encounters-story-profile__user .encounters-story-profile__age',
                'article.encounters-album .encounters-story-profile__age',
            ]
            
            # Extract name
            for selector in name_selectors:
                try:
                    name_elem = browser.find_element(By.CSS_SELECTOR, selector)
                    # Try textContent first (more reliable than .text)
                    try:
                        name_text = browser.execute_script("return arguments[0].textContent;", name_elem).strip()
                    except:
                        name_text = name_elem.text.strip()
                    
                    if name_text and 2 <= len(name_text) <= 50:
                        profile_data["name"] = name_text
                        print(f"{CYAN} Extracted name: {profile_data['name']}")
                        break
                except:
                    continue
            
            # Additional fallback: Try JavaScript extraction from profile_element
            if not profile_data.get("name"):
                try:
                    # Try to find name using JavaScript on the profile element
                    name_js_selectors = [
                        ".encounters-story-profile__name",
                        ".encounters-story-profile__user .encounters-story-profile__name",
                        "span.encounters-story-profile__name"
                    ]
                    for js_selector in name_js_selectors:
                        try:
                            name_text = browser.execute_script(
                                f"var elem = document.querySelector('{js_selector}'); return elem ? elem.textContent.trim() : null;"
                            )
                            if name_text and 2 <= len(name_text) <= 50:
                                profile_data["name"] = name_text
                                print(f"{CYAN} Extracted name (JavaScript fallback): {profile_data['name']}")
                                break
                        except:
                            continue
                except Exception as e:
                    print(f"{YELLOW} JavaScript name extraction fallback failed: {e}")
            
            # Extract age
            for selector in age_selectors:
                try:
                    age_elem = browser.find_element(By.CSS_SELECTOR, selector)
                    age_text = age_elem.text.strip()
                    # Remove comma and extract number (format: ", 28" or "28")
                    import re
                    age_match = re.search(r'(\d{2})', age_text)
                    if age_match:
                        age = int(age_match.group(1))
                        if 18 <= age <= 99:
                            profile_data["age"] = age
                            print(f"{CYAN} Extracted age: {profile_data['age']}")
                            break
                except:
                    continue
            
            # Fallback: try regex on article text if direct selectors failed
            if not profile_data.get("name") or not profile_data.get("age"):
                import re
                # Try both .text and JavaScript textContent for article text
                try:
                    article_text = browser.execute_script("return arguments[0].textContent;", profile_element)
                except:
                    article_text = profile_element.text
                
                # Try to find name/age pattern in text (e.g., "Kristine, 28")
                name_age_patterns = [
                    r'^([^\n,]+?)\s*,\s*(\d{2})\b',  # Start: "Name, 28"
                    r'([A-Z][a-zA-Z]+)\s*,\s*(\d{2})\b',  # Simple: "Name, 28"
                    r'^([A-Z][a-z]+)\s+(\d{2})\b',  # "Name 28" (no comma)
                ]
                
                for pattern in name_age_patterns:
                    match = re.search(pattern, article_text, re.MULTILINE)
                    if match:
                        name = match.group(1).strip()
                        name = re.sub(r'\s+', ' ', name).strip()
                        # Remove common non-name words
                        if name.lower() not in ['age', 'years', 'old', 'profile', 'about']:
                            age = int(match.group(2))
                            if 2 <= len(name) <= 50 and 18 <= age <= 99:
                                if not profile_data.get("name"):
                                    profile_data["name"] = name
                                if not profile_data.get("age"):
                                    profile_data["age"] = age
                                print(f"{CYAN} Extracted name/age (regex fallback): {profile_data.get('name')}, {profile_data.get('age')}")
                                break
        except Exception as e:
            print(f"{YELLOW} Error extracting name/age: {e}")
            # Don't set name/age to None - let validation handle it
            pass
        
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
        # Search entire page, not just profile_element, as bio is in encounters-story sections
        # NOTE: Not all profiles have bios - this is normal
        try:
            bio_selectors = [
                '.encounters-story-section--about .encounters-story-about__text',  # Primary: bio in "About" section
                '.encounters-story-about__text',  # Fallback
                '.encounters-story-section--about p',
                '.encounters-story-section__content p',
            ]
            bio_parts = []
            for selector in bio_selectors:
                try:
                    # Search entire page, not just profile_element
                    bio_elems = browser.find_elements(By.CSS_SELECTOR, selector)
                    for bio_elem in bio_elems:
                        try:
                            # Check if this is in the "About" section (not question answers)
                            parent = bio_elem.find_element(By.XPATH, './ancestor::section[contains(@class, "encounters-story-section")]')
                            section_class = parent.get_attribute('class') or ''
                            
                            # Only extract from "About" section, not question sections
                            if 'encounters-story-section--about' in section_class or 'encounters-story-section--question' not in section_class:
                                bio_text = bio_elem.text.strip()
                                # Filter out question answers (they're usually longer and have different structure)
                                if bio_text and bio_text not in bio_parts and len(bio_text) > 5:  # Allow shorter bios
                                    # Skip if it looks like a question answer (contains bullet points or multiple lines)
                                    if not (bio_text.count('\n') > 2 or bio_text.count('-') > 2):
                                        bio_parts.append(bio_text)
                        except:
                            # If we can't check parent, try to extract anyway but be more selective
                            try:
                                bio_text = bio_elem.text.strip()
                                if bio_text and len(bio_text) > 5 and len(bio_text) < 500:  # Reasonable bio length
                                    bio_parts.append(bio_text)
                            except:
                                continue
                except NoSuchElementException:
                    continue
            
            if bio_parts:
                # Join and clean up bio
                bio_text = '\n'.join(bio_parts).strip()
                profile_data["bio"] = bio_text
                print(f"{CYAN} Extracted bio: {len(bio_text)} characters")
            else:
                # No bio found - this is normal for some profiles
                profile_data["bio"] = None
                print(f"{CYAN} No bio found (this is normal for some profiles)")
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
            
            # Filter out badge/icon URLs - these contain specific patterns
            def is_profile_photo(src):
                if not src or len(src) < 50:
                    return False
                src_lower = src.lower()
                # Exclude badges, icons, and lifestyle badges
                if any(exclude in src_lower for exclude in [
                    'badge', 'icon', 'placeholder', 'lifestyle_badges', 
                    'profilechips', 'ic_badge', 'sz___size__'
                ]):
                    return False
                # Profile photos are typically in format like:
                # - //us1.ecdn2.bumbcdn.com/p521/hidden?euri=... (hidden photos)
                # - //us1.ecdn2.bumbcdn.com/i/big/... (visible photos)
                # Badge URLs contain: /assets/bumble_lifestyle_badges/
                if '/assets/bumble_lifestyle_badges/' in src_lower:
                    return False
                # Must be from bumbcdn.com or bumble.com
                if 'bumbcdn.com' not in src and 'bumble.com' not in src:
                    return False
                return True
            
            # First try to get images from the album (main profile images)
            try:
                album_elem = browser.find_element(By.CSS_SELECTOR, 'article.encounters-album')
                images = album_elem.find_elements(By.TAG_NAME, 'img')
                for img in images:
                    src = img.get_attribute('src') or img.get_attribute('data-src')
                    if src and src not in seen_urls and is_profile_photo(src):
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
                        if src and src not in seen_urls and is_profile_photo(src):
                            image_urls.append(src)
                            seen_urls.add(src)
                except:
                    continue
            
            # Limit to first 3 profile photos
            image_urls = image_urls[:3]
            
            profile_data["image_urls"] = list(set(image_urls))  # Remove duplicates
            if image_urls:
                print(f"{CYAN} Extracted {len(image_urls)} image(s)")
        except Exception as e:
            print(f"{YELLOW} Error extracting images: {e}")
            profile_data["image_urls"] = []
        
        # Extract location/distance - Bumble uses location-widget
        # HTML structure: .location-widget__town (city) and .location-widget__distance (distance)
        # Search entire page, not just profile_element
        try:
            # Wait a bit for location section to load
            time.sleep(1)
            
            location_parts = []
            
            # Extract city name
            try:
                town_elems = browser.find_elements(By.CSS_SELECTOR, '.location-widget__town')
                for town_elem in town_elems:
                    # Try multiple methods to get text
                    town_text = None
                    try:
                        town_text = town_elem.text.strip()
                    except:
                        pass
                    
                    if not town_text or len(town_text) < 1:
                        try:
                            town_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", town_elem)
                            town_text = town_text.strip() if town_text else ''
                        except:
                            pass
                    
                    if town_text and town_text not in location_parts:
                        location_parts.append(town_text)
                        print(f"{CYAN} Found location town: {town_text}")
            except Exception as e:
                print(f"{YELLOW} Error finding town: {e}")
            
            # Extract distance
            try:
                distance_elems = browser.find_elements(By.CSS_SELECTOR, '.location-widget__distance')
                for distance_elem in distance_elems:
                    # Try multiple methods to get text
                    distance_text = None
                    try:
                        distance_text = distance_elem.text.strip()
                    except:
                        pass
                    
                    if not distance_text or len(distance_text) < 1:
                        try:
                            distance_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", distance_elem)
                            distance_text = distance_text.strip() if distance_text else ''
                        except:
                            pass
                    
                    if distance_text and distance_text not in location_parts:
                        location_parts.append(distance_text)
                        print(f"{CYAN} Found location distance: {distance_text}")
            except Exception as e:
                print(f"{YELLOW} Error finding distance: {e}")
            
            # Fallback: try other selectors
            if not location_parts:
                location_selectors = [
                    '.encounters-story-section--location .location-widget__town',
                    '.encounters-story-section--location .location-widget__distance',
                    '[class*="location-widget"]',
                ]
                
                for selector in location_selectors:
                    try:
                        loc_elems = browser.find_elements(By.CSS_SELECTOR, selector)
                        for loc_elem in loc_elems:
                            try:
                                loc_text = loc_elem.text.strip()
                                if not loc_text:
                                    loc_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", loc_elem)
                                    loc_text = loc_text.strip() if loc_text else ''
                                if loc_text and loc_text not in location_parts:
                                    location_parts.append(loc_text)
                            except:
                                continue
                    except:
                        continue
            
            if location_parts:
                profile_data["location"] = ' | '.join(location_parts)
                print(f"{CYAN} Extracted location: {profile_data['location']}")
            else:
                profile_data["location"] = None
                print(f"{CYAN} No location found")
        except Exception as e:
            print(f"{YELLOW} Error extracting location: {e}")
            import traceback
            traceback.print_exc()
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
        
        # Extract ALL badges/pills (height, exercise, education, gender, intentions, family plans, politics, etc.)
        # Search entire page, not just profile_element
        # Badges are in .encounters-story-about__badge within the About section
        try:
            # Wait a bit for badges to load
            time.sleep(1)
            
            badge_selectors = [
                '.encounters-story-about__badge .pill__title',  # Primary: badge titles in About section
                '.encounters-story-section--about .pill__title',  # Alternative
                '.encounters-story-about__badge',  # Fallback
                '.pill[data-qa-role="pill"] .pill__title',
            ]
            
            all_badges = []
            seen_badges = set()
            for selector in badge_selectors:
                try:
                    badges = browser.find_elements(By.CSS_SELECTOR, selector)
                    print(f"{CYAN} Found {len(badges)} badge elements with selector: {selector}")
                    for badge in badges:
                        try:
                            # Try multiple methods to get badge text
                            badge_text = None
                            
                            # Method 1: Direct text property
                            try:
                                badge_text = badge.text.strip()
                            except:
                                pass
                            
                            # Method 2: JavaScript textContent (more reliable)
                            if not badge_text or len(badge_text) < 1:
                                try:
                                    badge_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", badge)
                                    if badge_text:
                                        # Handle encoding issues with emojis
                                        badge_text = badge_text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore').strip()
                                except:
                                    pass
                            
                            # Method 3: Try nested div with p-3 class
                            if not badge_text or len(badge_text) < 1:
                                try:
                                    nested_div = badge.find_element(By.CSS_SELECTOR, 'div.p-3, div[class*="p-3"], div')
                                    badge_text = nested_div.text.strip() if nested_div else ''
                                    if not badge_text:
                                        badge_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", nested_div)
                                        badge_text = badge_text.strip() if badge_text else ''
                                except:
                                    pass
                            
                            # Skip if it's an image URL or empty
                            if not badge_text or badge_text.startswith('http') or len(badge_text) < 1:
                                continue
                            
                            # Skip if it's just whitespace or very short
                            if len(badge_text) < 2:
                                continue
                            
                            # Normalize and deduplicate
                            badge_lower = badge_text.lower()
                            if badge_lower not in seen_badges:
                                seen_badges.add(badge_lower)
                                all_badges.append(badge_text)
                                safe_print(f"{CYAN}   Added badge: {badge_text}")
                        except Exception as e:
                            safe_print(f"{YELLOW}   Error processing badge: {e}")
                            continue
                except Exception as e:
                    print(f"{YELLOW} Error with selector {selector}: {e}")
                    continue
            
            if all_badges:
                profile_data["badges"] = all_badges
                print(f"{CYAN} Extracted {len(all_badges)} badge(s): {', '.join(all_badges[:5])}{'...' if len(all_badges) > 5 else ''}")
            else:
                profile_data["badges"] = []
                print(f"{YELLOW} No badges found")
        except Exception as e:
            print(f"{YELLOW} Error extracting badges: {e}")
            import traceback
            traceback.print_exc()
            profile_data["badges"] = []
        
        # Extract question answers (e.g., "Two truths and a lie", "My simple pleasures are")
        # Search entire page, not just profile_element
        try:
            # Wait a bit for question sections to load
            time.sleep(1)
            
            question_sections = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-section--question')
            print(f"{CYAN} Found {len(question_sections)} question section(s)")
            questions_answers = {}
            
            for i, section in enumerate(question_sections):
                try:
                    # Get question title - try multiple methods
                    question_title = None
                    try:
                        question_title_elem = section.find_element(By.CSS_SELECTOR, '.encounters-story-section__heading-title h2')
                        question_title = question_title_elem.text.strip() if question_title_elem else None
                        if not question_title:
                            question_title = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", question_title_elem)
                            question_title = question_title.strip() if question_title else None
                    except:
                        # Try alternative selector
                        try:
                            question_title_elem = section.find_element(By.CSS_SELECTOR, '.encounters-story-section__heading-title')
                            question_title = question_title_elem.text.strip() if question_title_elem else None
                            if not question_title:
                                question_title = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", question_title_elem)
                                question_title = question_title.strip() if question_title else None
                        except:
                            pass
                    
                    # Get answer text - try multiple methods
                    answer_text = None
                    try:
                        answer_elem = section.find_element(By.CSS_SELECTOR, '.encounters-story-about__text')
                        answer_text = answer_elem.text.strip() if answer_elem else None
                        if not answer_text:
                            answer_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", answer_elem)
                            answer_text = answer_text.strip() if answer_text else None
                    except:
                        # Try alternative selector
                        try:
                            answer_elem = section.find_element(By.CSS_SELECTOR, '.encounters-story-section__content p, .encounters-story-section__content')
                            answer_text = answer_elem.text.strip() if answer_elem else None
                            if not answer_text:
                                answer_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", answer_elem)
                                answer_text = answer_text.strip() if answer_text else None
                        except:
                            pass
                    
                    if question_title and answer_text:
                        questions_answers[question_title] = answer_text
                        print(f"{CYAN}   Extracted Q&A: {question_title[:40]}...")
                except Exception as e:
                    print(f"{YELLOW}   Error processing question section {i}: {e}")
                    continue
            
            if questions_answers:
                profile_data["question_answers"] = questions_answers
                print(f"{CYAN} Extracted {len(questions_answers)} question answer(s)")
            else:
                profile_data["question_answers"] = {}
                print(f"{CYAN} No question answers found")
        except Exception as e:
            print(f"{YELLOW} Error extracting question answers: {e}")
            import traceback
            traceback.print_exc()
            profile_data["question_answers"] = {}
        
        # Extract Spotify artists - search entire page
        try:
            spotify_artists = []
            spotify_widget = browser.find_elements(By.CSS_SELECTOR, '.spotify-widget__artist')
            
            for artist in spotify_widget:
                try:
                    # Don't require is_displayed() - elements might be in DOM but not visible
                    artist_name_elem = artist.find_element(By.CSS_SELECTOR, '.spotify-widget__artist-name')
                    artist_name = artist_name_elem.text.strip() if artist_name_elem else None
                    if artist_name and artist_name not in spotify_artists:
                        spotify_artists.append(artist_name)
                except:
                    continue
            
            if spotify_artists:
                profile_data["spotify_artists"] = spotify_artists
                print(f"{CYAN} Extracted {len(spotify_artists)} Spotify artist(s)")
        except Exception as e:
            print(f"{YELLOW} Error extracting Spotify artists: {e}")
            profile_data["spotify_artists"] = []
        
        # Extract "From" location (e.g., "🇺🇸 Lives in Denver, CO")
        # HTML structure: .location-widget__pill .pill__title
        # Search entire page
        try:
            from_location_selectors = [
                '.location-widget__pill .pill__title',  # Found in HTML
                '.encounters-story-section--location .location-widget__pill .pill__title',
                '.location-widget__info .pill__title',
                '.location-widget__pill .pill__title div',  # Nested structure
            ]
            
            from_locations = []
            for selector in from_location_selectors:
                try:
                    pills = browser.find_elements(By.CSS_SELECTOR, selector)
                    print(f"{CYAN} Found {len(pills)} pill(s) with selector: {selector}")
                    for pill in pills:
                        try:
                            # Try multiple methods to get text
                            pill_text = None
                            
                            # Method 1: Direct text property
                            try:
                                pill_text = pill.text.strip()
                            except:
                                pass
                            
                            # Method 2: JavaScript textContent
                            if not pill_text or len(pill_text) < 1:
                                try:
                                    pill_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", pill)
                                    if pill_text:
                                        # Handle encoding issues with emojis
                                        pill_text = pill_text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore').strip()
                                except:
                                    pass
                            
                            # Method 3: Try nested div
                            if not pill_text or len(pill_text) < 1:
                                try:
                                    nested_div = pill.find_element(By.CSS_SELECTOR, 'div.p-3, div[class*="p-3"], div')
                                    pill_text = nested_div.text.strip() if nested_div else ''
                                    if not pill_text:
                                        pill_text = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", nested_div)
                                        if pill_text:
                                            # Handle encoding issues with emojis
                                            pill_text = pill_text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore').strip()
                                except:
                                    pass
                            
                            # Check for location indicators (flags, "Lives in", "From")
                            if pill_text and any(indicator in pill_text.lower() for indicator in ['lives in', 'from', '🇺🇸', '🇬🇧', '🇨🇦', '🇲🇽', '🇦🇺']):
                                from_locations.append(pill_text)
                                safe_print(f"{CYAN} Found from location: {pill_text}")
                        except Exception as e:
                            safe_print(f"{YELLOW} Error processing pill: {e}")
                            continue
                    if from_locations:
                        break
                except Exception as e:
                    print(f"{YELLOW} Error with selector {selector}: {e}")
                    continue
            
            # Also check badges for location info (sometimes it's there)
            # This is more reliable since badges are already extracted with proper encoding
            # Check badges even if direct extraction found something, to ensure we get the best match
            if profile_data.get("badges"):
                for badge in profile_data["badges"]:
                    badge_lower = badge.lower()
                    # Look for "from" location (not "lives in")
                    if 'from' in badge_lower and 'lives in' not in badge_lower:
                        from_locations.append(badge)
                        safe_print(f"{CYAN} Found from location in badges: {badge}")
                        break  # Take first "From" location found
            
            if from_locations:
                # Prefer "From" over "Lives in" if both exist
                from_location = None
                for loc in from_locations:
                    if 'from' in loc.lower() and 'lives in' not in loc.lower():
                        from_location = loc
                        break
                if not from_location:
                    from_location = from_locations[0]
                profile_data["from_location"] = from_location
                safe_print(f"{CYAN} Extracted from location: {profile_data['from_location']}")
            else:
                profile_data["from_location"] = None
                print(f"{CYAN} No from location found")
        except Exception as e:
            print(f"{YELLOW} Error extracting from location: {e}")
            import traceback
            traceback.print_exc()
            profile_data["from_location"] = None
        
        # Extract job from encounters-story-profile__occupation if not already found
        if not profile_data.get("job"):
            try:
                occupation_elem = browser.find_element(By.CSS_SELECTOR, '.encounters-story-profile__occupation')
                job_text = occupation_elem.text.strip() if occupation_elem else None
                if job_text:
                    profile_data["job"] = job_text
                    print(f"{CYAN} Extracted job from occupation field: {profile_data['job']}")
            except:
                pass
        
        # Create fingerprint BEFORE name validation (for loop detection even when name is missing)
        # This allows us to detect loops even when name extraction fails
        profile_fingerprint = create_profile_fingerprint(profile_data)
        profile_data["_fingerprint"] = profile_fingerprint  # Store fingerprint for loop detection
        
        # Final attempt: Try to extract name from the entire article text using regex
        if not profile_data.get("name"):
            try:
                import re
                # Get full article text
                try:
                    article_text = browser.execute_script("return arguments[0].textContent;", profile_element)
                except:
                    article_text = profile_element.text
                
                # Look for name patterns at the start of the text
                # Common patterns: "Name, 28" or "Name 28" or just "Name" at the beginning
                name_patterns = [
                    r'^([A-Z][a-z]{2,20})\s*,?\s*\d{2}',  # "Name, 28" or "Name 28"
                    r'^([A-Z][a-z]{2,20})\s+',  # "Name " at start
                    r'([A-Z][a-z]{2,20})\s*,\s*\d{2}',  # "Name, 28" anywhere
                ]
                
                for pattern in name_patterns:
                    match = re.search(pattern, article_text, re.MULTILINE)
                    if match:
                        potential_name = match.group(1).strip()
                        # Filter out common non-name words
                        if (potential_name.lower() not in ['age', 'years', 'old', 'profile', 'about', 'lives', 'from', 
                                                           'seattle', 'washington', 'denver', 'colorado', 'woman', 'man',
                                                           'relationship', 'never', 'sometimes', 'frequently', 'socially'] and
                            2 <= len(potential_name) <= 30):
                            profile_data["name"] = potential_name
                            print(f"{CYAN} Extracted name (final regex attempt): {profile_data['name']}")
                            break
            except Exception as e:
                print(f"{YELLOW} Final name extraction attempt failed: {e}")
        
        # If still no name, generate a placeholder name from available data
        profile_name = profile_data.get("name")
        if not profile_name or not isinstance(profile_name, str) or not profile_name.strip() or profile_name.lower() in ['none', 'null', 'undefined']:
            # Generate placeholder name from age and location
            age = profile_data.get("age", "?")
            location = profile_data.get("location", "Unknown")
            # Extract city name from location (e.g., "Seattle, Washington" -> "Seattle")
            city = location.split(',')[0].strip() if location and ',' in location else location
            profile_data["name"] = f"Unknown_{age}_{city}".replace(' ', '_')[:50]
            profile_data["_name_placeholder"] = True  # Flag to indicate this is a placeholder
            print(f"{YELLOW} Warning: Could not extract name - using placeholder: {profile_data['name']}")
            print(f"{YELLOW} Debug: Extracted fields: {[k for k in profile_data.keys() if k not in ['extracted_at', '_fingerprint', '_name_placeholder']]}")
        
        # Remove fingerprint from profile_data before returning (it's internal)
        profile_data.pop("_fingerprint", None)
        
        # Print extracted data summary
        print(f"{GREEN} Profile extracted: {profile_data.get('name', 'Unknown')} ({profile_data.get('age', '?')})")
        
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
        
        # Grant geolocation permission first
        try:
            browser.execute_cdp_cmd('Browser.grantPermissions', {
                'origin': 'https://bumble.com',
                'permissions': ['geolocation']
            })
            browser.execute_cdp_cmd('Browser.grantPermissions', {
                'origin': 'https://www.bumble.com',
                'permissions': ['geolocation']
            })
        except:
            pass  # Permissions may already be granted
        
        # Set geolocation override
        browser.execute_cdp_cmd('Emulation.setGeolocationOverride', {
            'latitude': coords['latitude'],
            'longitude': coords['longitude'],
            'accuracy': 100
        })
        
        # Also set timezone to match location (helps with location detection)
        try:
            # Get timezone for location
            timezone_map = {
                'seattle': 'America/Los_Angeles',
                'denver': 'America/Denver',
                'new york': 'America/New_York',
                'los angeles': 'America/Los_Angeles',
                'chicago': 'America/Chicago',
                'san francisco': 'America/Los_Angeles',
                'austin': 'America/Chicago',
                'miami': 'America/New_York',
            }
            location_lower = location.lower().strip()
            city_name = location_lower.split(',')[0].strip()
            timezone = timezone_map.get(city_name, 'America/Los_Angeles')
            
            browser.execute_cdp_cmd('Emulation.setTimezoneOverride', {
                'timezoneId': timezone
            })
            print(f"{CYAN} Also set timezone to: {timezone}")
        except Exception as e:
            print(f"{YELLOW} Could not set timezone: {e}")
        
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
        # IMPORTANT: "Lives in" location is different from search/matching location
        # We need to find the "Discovery location" or "Search location" setting, not just "Lives in"
        print(f"{CYAN} Navigating to Bumble settings...")
        print(f"{YELLOW} Note: 'Lives in' location is different from search/matching location.")
        print(f"{YELLOW} We need to find 'Discovery location' or 'Search location' setting.")
        
        # Try multiple ways to access settings:
        # 1. Direct URL
        settings_urls = [
            "https://www.bumble.com/app/settings",
            "https://app.bumble.com/settings",
            "https://www.bumble.com/app/preferences",
            "https://www.bumble.com/app/settings/location",  # Direct location settings
            "https://app.bumble.com/settings/location",
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
            # Try to access filters directly from the app page
            try:
                # First, make sure we're on the app page
                if 'app' not in browser.current_url:
                    browser.get("https://www.bumble.com/app")
                    time.sleep(3)
                
                # Look for filter button - Bumble has a filters button on the main app page
                filter_selectors = [
                    'button[aria-label*="Filter"]',
                    'button[aria-label*="filter"]',
                    'button[class*="filter"]',
                    '[data-testid*="filter"]',
                    'button[class*="encounters-controls"]',  # Filter might be in controls
                    'a[href*="filter"]',
                    'a[href*="settings"]',
                ]
                
                for selector in filter_selectors:
                    try:
                        filter_btn = browser.find_element(By.CSS_SELECTOR, selector)
                        if filter_btn.is_displayed():
                            filter_btn.click()
                            time.sleep(2)
                            print(f"{GREEN} Opened filters/settings")
                            settings_accessed = True
                            break
                    except:
                        continue
            except Exception as e:
                print(f"{YELLOW} Error accessing filters: {e}")
        
        # Try to find location input/selector
        # Look for "Discovery location", "Search location", or "Location" settings
        # NOT "Lives in" - that's just a profile field
        print(f"{CYAN} Looking for location input field (Discovery/Search location, not 'Lives in')...")
        location_selectors = [
            'input[placeholder*="discovery location" i]',
            'input[placeholder*="search location" i]',
            'input[placeholder*="location" i]',
            'input[placeholder*="city" i]',
            'input[name*="discovery" i]',
            'input[name*="search" i]',
            'input[name*="location" i]',
            'input[id*="discovery" i]',
            'input[id*="search" i]',
            'input[id*="location" i]',
            'input[type="text"][class*="location"]',
            'select[name*="location" i]',
            'select[id*="location" i]',
            # Also look for buttons/links that might open location picker
            'button[aria-label*="change location" i]',
            'button[aria-label*="update location" i]',
            'button[aria-label*="location" i]',
            'a[href*="location"]',
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
            print(f"{YELLOW} Could not find location input field.")
            print(f"{YELLOW} IMPORTANT: 'Lives in' location in profile settings does NOT change which profiles you see.")
            print(f"{YELLOW} Bumble uses IP-based geolocation for matching, which overrides browser geolocation.")
            print(f"{YELLOW} To get Seattle profiles with web scraper, you need:")
            print(f"{YELLOW}   1. A VPN/proxy with a Seattle IP address (most reliable for web scraping)")
            print(f"{YELLOW}   2. Bumble Premium Travel Mode (mobile app only - NOT available on web)")
            print(f"{YELLOW}   3. Or manually change 'Discovery location' in Bumble settings (if available)")
            print(f"{YELLOW} See TRAVEL_MODE.md for detailed information about location options.")
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


def save_profile_to_notion(profile_data: Dict, backend_root: str = None) -> bool:
    """
    Save a profile to Notion using the Node.js script with retry logic.
    Returns True if successful, False otherwise.
    """
    try:
        # Find backend root (parent of submodules)
        if not backend_root:
            current_dir = Path(__file__).resolve()
            # Go up: Scraper -> bumble-auto-liker -> submodules -> backend
            # Path structure: backend/submodules/bumble-auto-liker/Scraper/bumble_profile_scraper.py
            backend_root = current_dir.parent.parent.parent.parent
        
        script_path = Path(backend_root) / 'scripts' / 'save-bumble-profile-to-notion.ts'
        
        if not script_path.exists():
            print(f"{YELLOW} ⚠️  Notion save script not found at {script_path}, skipping Notion save")
            return False
        
        # Convert profile data to JSON
        profile_json = json.dumps(profile_data, ensure_ascii=False)
        
        # Call Node.js script via subprocess
        # Use pnpm or node directly
        result = None
        try:
            # Try pnpm first (if available)
            result = subprocess.run(
                ['pnpm', 'tsx', str(script_path)],
                input=profile_json,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid characters instead of failing
                capture_output=True,
                timeout=60,  # Increased timeout for retry logic
                cwd=str(backend_root),
                env=os.environ.copy()  # Pass environment variables (including NOTION_TOKEN)
            )
        except FileNotFoundError:
            # Fallback to npx with tsx
            try:
                result = subprocess.run(
                    ['npx', 'tsx', str(script_path)],
                    input=profile_json,
                    text=True,
                    encoding='utf-8',
                    errors='replace',  # Replace invalid characters instead of failing
                    capture_output=True,
                    timeout=60,
                    cwd=str(backend_root),
                    env=os.environ.copy()
                )
            except FileNotFoundError:
                print(f"{YELLOW} ⚠️  Could not execute Notion save script (pnpm/npx not found), skipping Notion save")
                return False
        except subprocess.TimeoutExpired:
            profile_name = profile_data.get('name', 'Unknown')
            print(f"{YELLOW} ⏱️  Notion save script timed out for {profile_name} (may be retrying), skipping Notion save")
            return False
        
        if result and result.returncode == 0:
            # Check output for success/duplicate messages
            output = result.stdout.strip()
            if '✅ Saved:' in output or '⏭️  Duplicate:' in output:
                # Print without the script's own log prefix to avoid duplication
                lines = [line for line in output.split('\n') if line.strip() and not line.startswith('✅ Loaded')]
                if lines:
                    # Replace "✅ Saved:" with "✅ Saved to Notion:"
                    last_line = lines[-1]
                    if '✅ Saved:' in last_line:
                        last_line = last_line.replace('✅ Saved:', '✅ Saved to Notion:')
                    print(f"{CYAN} {last_line}")  # Print last line (the result)
                return True
            else:
                # Unexpected success output
                if output:
                    print(f"{CYAN} ✅ Saved to Notion: {output}")
                return True
        elif result:
            error_output = result.stderr.strip() or result.stdout.strip()
            # Don't print error if it's just a duplicate or validation error (these are expected)
            if 'duplicate' in error_output.lower() or 'validation' in error_output.lower() or 'Skipping profile' in error_output:
                lines = [line for line in error_output.split('\n') if line.strip() and not line.startswith('✅ Loaded')]
                if lines:
                    print(f"{CYAN} {lines[-1]}")
                return True
            else:
                # Real error - show better feedback with emojis
                error_lines = [line for line in error_output.split('\n') if '❌' in line or 'Error' in line or 'error' in line.lower()]
                if error_lines:
                    error_msg = error_lines[0]
                    # Extract profile name if available
                    profile_name = profile_data.get('name', 'Unknown')
                    print(f"{RED} ❌ Failed to save {profile_name} to Notion: {error_msg}")
                else:
                    # Generic error message
                    profile_name = profile_data.get('name', 'Unknown')
                    print(f"{RED} ❌ Failed to save {profile_name} to Notion: {error_output[:200]}")
                return False
        else:
            return False
                
    except Exception as e:
        # Try to get profile name from profile_data if available
        try:
            profile_name = profile_data.get('name', 'Unknown') if profile_data else 'Unknown'
        except:
            profile_name = 'Unknown'
        error_msg = str(e)
        print(f"{RED} ❌ Error saving {profile_name} to Notion: {error_msg}")
        return False


def create_profile_fingerprint(profile_data: Dict) -> str:
    """
    Create a unique fingerprint for a profile based on extracted data.
    Used to detect when we're extracting the same profile repeatedly.
    
    Args:
        profile_data: Dictionary containing extracted profile data
        
    Returns:
        A string fingerprint representing the profile
    """
    try:
        # Extract key identifying features
        age = profile_data.get("age", "unknown")
        location = profile_data.get("location", "unknown")
        
        # Sort badges for consistent fingerprinting
        badges = sorted(profile_data.get("badges", [])) if isinstance(profile_data.get("badges"), list) else []
        badges_str = ",".join(badges)
        
        # Use question answer keys (not values, as they might vary)
        qa_keys = sorted(profile_data.get("question_answers", {}).keys()) if isinstance(profile_data.get("question_answers"), dict) else []
        qa_keys_str = ",".join(qa_keys)
        
        # Image URLs count
        image_count = len(profile_data.get("image_urls", [])) if isinstance(profile_data.get("image_urls"), list) else 0
        
        # Create fingerprint
        fingerprint_parts = [
            f"age:{age}",
            f"loc:{location}",
            f"badges:{badges_str}",
            f"qa:{qa_keys_str}",
            f"imgs:{image_count}"
        ]
        
        return "|".join(fingerprint_parts)
    except Exception as e:
        print(f"{YELLOW} Error creating profile fingerprint: {e}")
        return "error"


def save_stuck_profile_html(browser: webdriver.Chrome, profile_count: int) -> str:
    """
    Save the current browser page HTML to a file for debugging stuck profiles.
    
    Args:
        browser: Selenium WebDriver instance
        profile_count: Current profile count for filename
        
    Returns:
        Path to the saved HTML file
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"bumble_stuck_profile_{timestamp}_profile{profile_count}.html"
        
        # Get page source
        page_source = browser.page_source
        
        # Save to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(page_source)
        
        print(f"{YELLOW} Saved stuck profile HTML to: {filename}")
        return filename
    except Exception as e:
        print(f"{YELLOW} Error saving stuck profile HTML: {e}")
        return ""


def restart_browser(browser: webdriver.Chrome, cookie_file: str = None, headless: bool = True, 
                    location: str = None, chrome_version: int = None) -> webdriver.Chrome:
    """
    Restart the browser by closing the current instance and creating a new one.
    Reloads cookies and sets location if provided.
    
    Args:
        browser: Current browser instance to close
        cookie_file: Path to cookie file to reload
        headless: Whether to run in headless mode
        location: Location to set after restart
        chrome_version: Chrome version to use
        
    Returns:
        New browser instance
    """
    try:
        print(f"{CYAN} Restarting browser...")
        
        # Close current browser
        try:
            browser.quit()
        except Exception as e:
            print(f"{YELLOW} Error closing browser: {e}")
        
        # Wait a bit before restarting
        time.sleep(2)
        
        # Reinitialize browser using existing logic
        def create_chrome_options():
            """Create a new ChromeOptions object (cannot be reused)"""
            options = uc.ChromeOptions()
            # Incremental fix 3: Use --headless=old instead of --headless=new (more reliable on Windows)
            if headless:
                options.add_argument('--headless=old')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            return options
        
        # Create new browser instance
        if chrome_version:
            options = create_chrome_options()
            # Incremental fix 2: Disable use_subprocess when headless (may interfere with headless mode)
            new_browser = uc.Chrome(options=options, version_main=chrome_version, headless=headless, use_subprocess=not headless)
        else:
            options = create_chrome_options()
            # Incremental fix 2: Disable use_subprocess when headless (may interfere with headless mode)
            new_browser = uc.Chrome(options=options, version_main=None, headless=headless, use_subprocess=not headless)
        
        print(f"{GREEN} Browser restarted successfully")
        
        # Navigate to app
        new_browser.get("https://www.bumble.com/app")
        time.sleep(3)
        
        # Reload cookies if provided
        if cookie_file:
            cookies = load_cookies_from_file(cookie_file)
            if cookies:
                if inject_cookies_to_browser(new_browser, cookies):
                    print(f"{GREEN} Cookies reloaded successfully")
                    # Refresh page after cookies
                    new_browser.get("https://www.bumble.com/app")
                    time.sleep(3)
        
        # Set location if provided
        if location:
            set_location(new_browser, location)
        
        return new_browser
        
    except Exception as e:
        print(f"{RED} Error restarting browser: {e}")
        raise


def save_profile_to_json(profile_data: Dict, json_file: str) -> bool:
    """
    Save a single profile to JSON file incrementally (append mode).
    Creates file if it doesn't exist, appends if it does.
    Returns True if successful, False otherwise.
    """
    try:
        # Read existing profiles if file exists
        existing_profiles = []
        if Path(json_file).exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_profiles = json.load(f)
                    if not isinstance(existing_profiles, list):
                        existing_profiles = []
            except (json.JSONDecodeError, IOError):
                existing_profiles = []
        
        # Add new profile
        existing_profiles.append(profile_data)
        
        # Write back to file
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(existing_profiles, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"{YELLOW} Error saving profile to JSON: {e}")
        return False


def scrape_profiles(cookie_file: str = None, limit: int = None, delay: float = 1.5,
                    output_format: str = 'json', output_file: str = None, headless: bool = True,
                    location: str = None, no_swipe: bool = False, keep_browser_open: bool = False,
                    save_to_notion: bool = False, gender: str = None):
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
        no_swipe: If True, extract data without swiping (default: False - will swipe after extraction)
        save_to_notion: If True, save each profile to Notion with retry logic
        gender: Optional gender to set for all scraped profiles (e.g., "female", "male", "non-binary")
    """
    browser = None
    try:
        print(f"{CYAN} Initializing Bumble scraper...")
        if no_swipe:
            print(f"{CYAN} Mode: Extract profile data ONLY (no swiping)")
        else:
            print(f"{CYAN} Mode: Extract profile data BEFORE swiping right")
        print(f"{CYAN} Headless: {headless}")
        if gender:
            print(f"{CYAN} Gender: {gender} (will be set for all scraped profiles)")
        if save_to_notion:
            print(f"{CYAN} Notion saving: ENABLED (each profile saved to JSON backup first, then to Notion with retry logic)")
        else:
            print(f"{CYAN} Notion saving: DISABLED (profiles will be saved to JSON file only)")
        
        def create_chrome_options():
            """Create a new ChromeOptions object (cannot be reused)"""
            options = uc.ChromeOptions()
            # Use --headless=old instead of --headless=new (more reliable on Windows)
            if headless:
                options.add_argument('--headless=old')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            return options
        
        # Create undetected Chrome driver (undetected-chromedriver handles anti-detection automatically)
        # Let undetected-chromedriver auto-detect and download the correct ChromeDriver version
        # Note: This scraper uses Chrome regardless of where cookies came from (Firefox/Chrome/etc)
        # Cookies are browser-agnostic HTTP cookies, so Firefox cookies work fine in Chrome
        print(f"{CYAN} Starting browser...")
        if headless:
            print(f"{CYAN} Running in headless mode (no visible browser window)")
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
                                # Fix: Add headless arguments to prevent Chrome from opening visibly during version detection
                                version_args = [chrome_path, '--version']
                                if headless:
                                    version_args.extend(['--headless=old', '--disable-gpu', '--no-sandbox'])
                                result = subprocess.run(
                                    version_args,
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
                # Disable use_subprocess when headless (may interfere with headless mode)
                browser = uc.Chrome(options=options, version_main=chrome_version, headless=headless, use_subprocess=not headless)
            else:
                print(f"{CYAN} Using auto-detection for Chrome version...")
                options = create_chrome_options()
                # Disable use_subprocess when headless (may interfere with headless mode)
                browser = uc.Chrome(options=options, version_main=None, headless=headless, use_subprocess=not headless)
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
                        # Incremental fix 2: Disable use_subprocess when headless (may interfere with headless mode)
                        browser = uc.Chrome(options=options, version_main=chrome_version, headless=headless, use_subprocess=not headless)
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
        # IMPORTANT: Bumble uses IP-based geolocation primarily, so browser geolocation may not fully override it
        # However, we'll try multiple methods to set location:
        # 1. Browser geolocation API (Chrome DevTools Protocol)
        # 2. Bumble settings/filters UI
        # 3. Note: If your IP address is in Denver, Bumble will likely show Denver profiles regardless
        # NOTE: "Lives in" location in profile settings is different from search/matching location
        # Bumble may still use IP-based geolocation for matching even if "Lives in" is set to Seattle
        # 
        # TRAVEL MODE NOTE:
        # - Bumble Premium Travel Mode allows changing location to any city (7 days)
        # - However, Travel Mode is NOT available on Bumble Web (only mobile app)
        # - For web scraping, you need a VPN/proxy with target city IP address
        # - See TRAVEL_MODE.md for more details
        if location:
            print(f"{CYAN} Attempting to set location to: {location}")
            print(f"{YELLOW} Note: Bumble primarily uses IP-based geolocation for matching.")
            print(f"{YELLOW} 'Lives in' location in profile settings is different from search/matching location.")
            print(f"{YELLOW} If your IP is in Denver, you may still see Denver profiles even after setting location.")
            print(f"{YELLOW} Travel Mode (Bumble Premium) is NOT available on Bumble Web (mobile app only).")
            print(f"{YELLOW} To get Seattle profiles with web scraper, you need a VPN/proxy with a Seattle IP address.")
            print(f"{YELLOW} See TRAVEL_MODE.md for more information about location options.")
            
            location_set = set_location(browser, location)
            if location_set:
                print(f"{GREEN} Location setting attempted.")
                print(f"{CYAN} Refreshing app page to apply location change...")
                # Navigate away and back to force refresh
                browser.get("https://www.bumble.com")
                time.sleep(2)
                browser.get("https://www.bumble.com/app")
                time.sleep(5)  # Wait longer for location to take effect
                print(f"{CYAN} App page refreshed. Profiles shown may still be based on IP address.")
            else:
                print(f"{YELLOW} Location setting failed. Bumble may require manual location change in settings.")
                print(f"{YELLOW} If you manually set 'Lives in' to Seattle, note that this may not change matching location.")
                print(f"{YELLOW} Bumble may have a separate 'Discovery location' or 'Search location' setting.")
            
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
        consecutive_failures = 0
        max_consecutive_failures = 3  # Stop after 3 consecutive failures
        daily_limit_hit = False  # Track if we hit the daily limit gracefully
        
        # Loop detection: Track recent profile fingerprints to detect infinite loops
        recent_profile_fingerprints = []
        max_loop_detection_count = 3  # Number of same fingerprints before restart
        max_restarts = 3  # Maximum browser restarts per session
        restart_count = 0
        
        # Initialize JSON file path for incremental saving (backup)
        json_backup_file = None
        if output_format == 'json':
            if not output_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                suffix = '_backup' if save_to_notion else ''
                json_backup_file = f"bumble_profiles_{timestamp}{suffix}.json"
            else:
                json_backup_file = output_file
            # Initialize empty JSON file
            try:
                with open(json_backup_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
                print(f"{CYAN} Initialized JSON backup file: {json_backup_file}")
            except Exception as e:
                print(f"{YELLOW} Warning: Could not initialize JSON backup file: {e}")
                json_backup_file = None
        
        while True:
            # Check limit
            if limit and profile_count >= limit:
                print(f"{CYAN} Reached limit of {limit} profiles")
                break
            
            print(f"{CYAN} Profile {profile_count + 1}: Extracting data...")
            
            # Extract profile data BEFORE swiping
            profile_data = extract_profile_data(browser, gender=gender)
            
            # Create fingerprint for loop detection (even if name is missing)
            # We need to extract partial data to create fingerprint even when name extraction fails
            current_fingerprint = None
            if profile_data:
                # Profile data is valid (has name)
                current_fingerprint = profile_data.get("_fingerprint") or create_profile_fingerprint(profile_data)
            else:
                # Profile data is None (name missing), but we still need to detect loops
                # Try to extract partial data for fingerprinting
                try:
                    # Quick extraction of key fields for fingerprinting
                    partial_data = {}
                    try:
                        age_elem = browser.find_element(By.CSS_SELECTOR, '.encounters-story-profile__age')
                        age_text = age_elem.text.strip()
                        import re
                        age_match = re.search(r'(\d{2})', age_text)
                        if age_match:
                            partial_data["age"] = int(age_match.group(1))
                    except:
                        pass
                    
                    try:
                        location_elem = browser.find_element(By.CSS_SELECTOR, '.location-widget__town')
                        partial_data["location"] = location_elem.text.strip() if location_elem else None
                    except:
                        pass
                    
                    try:
                        badge_elems = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-about__badge .pill__title')
                        partial_data["badges"] = [badge.text.strip() for badge in badge_elems if badge.text.strip()]
                    except:
                        pass
                    
                    try:
                        # Extract question titles (keys) for fingerprinting
                        qa_sections = browser.find_elements(By.CSS_SELECTOR, '.encounters-story-section--question')
                        qa_dict = {}
                        for section in qa_sections:
                            try:
                                question_title_elem = section.find_element(By.CSS_SELECTOR, '.encounters-story-section__heading-title h2, .encounters-story-section__heading-title')
                                question_title = question_title_elem.text.strip() if question_title_elem else None
                                if not question_title:
                                    question_title = browser.execute_script("return arguments[0].textContent || arguments[0].innerText || '';", question_title_elem)
                                    question_title = question_title.strip() if question_title else None
                                if question_title:
                                    qa_dict[question_title] = "exists"
                            except:
                                pass
                        if qa_dict:
                            partial_data["question_answers"] = qa_dict
                    except Exception as e:
                        print(f"{YELLOW} Error extracting question answers for fingerprint: {e}")
                        pass
                    
                    try:
                        img_elems = browser.find_elements(By.CSS_SELECTOR, '.encounters-album__photo img')
                        partial_data["image_urls"] = [img.get_attribute('src') for img in img_elems[:3] if img.get_attribute('src')]
                    except:
                        pass
                    
                    if partial_data:
                        current_fingerprint = create_profile_fingerprint(partial_data)
                        print(f"{CYAN} Created fingerprint from partial data (name missing): {current_fingerprint[:80]}...")
                        print(f"{CYAN} Recent fingerprints count: {len(recent_profile_fingerprints)}")
                    else:
                        print(f"{YELLOW} Warning: Could not extract any partial data for fingerprinting")
                except Exception as e:
                    print(f"{YELLOW} Could not create fingerprint from partial data: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Check for infinite loop: same profile extracted repeatedly
            if current_fingerprint:
                print(f"{CYAN} Current fingerprint: {current_fingerprint[:80]}...")
                print(f"{CYAN} Recent fingerprints: {[fp[:40] + '...' if len(fp) > 40 else fp for fp in recent_profile_fingerprints[-3:]]}")
                if len(recent_profile_fingerprints) >= max_loop_detection_count:
                    # Check if last N fingerprints are the same
                    recent_same = all(fp == current_fingerprint for fp in recent_profile_fingerprints[-max_loop_detection_count:])
                    if recent_same:
                        print(f"{RED} ERROR: Infinite loop detected - same profile extracted {max_loop_detection_count} times consecutively")
                        print(f"{YELLOW} Fingerprint: {current_fingerprint}")
                        
                        # Save HTML for debugging
                        html_file = save_stuck_profile_html(browser, profile_count)
                        
                        # Restart browser if enabled and under limit
                        if restart_count < max_restarts:
                            restart_count += 1
                            print(f"{CYAN} Attempting browser restart ({restart_count}/{max_restarts})...")
                            try:
                                browser = restart_browser(browser, cookie_file, headless, location, chrome_version)
                                # Clear fingerprint history after restart
                                recent_profile_fingerprints = []
                                consecutive_failures = 0
                                print(f"{GREEN} Browser restarted successfully, continuing...")
                                time.sleep(5)  # Wait for page to load
                                continue  # Skip to next iteration
                            except Exception as e:
                                print(f"{RED} Browser restart failed: {e}")
                                print(f"{YELLOW} Stopping scraper to prevent infinite restart loop")
                                break
                        else:
                            print(f"{RED} Maximum restart limit ({max_restarts}) reached. Stopping scraper.")
                            break
                
                # Add current fingerprint to recent list (keep last 5)
                recent_profile_fingerprints.append(current_fingerprint)
                if len(recent_profile_fingerprints) > 5:
                    recent_profile_fingerprints.pop(0)
            
            if not profile_data:
                consecutive_failures += 1
                print(f"{YELLOW} Warning: Could not extract profile data - no profile visible (failure {consecutive_failures}/{max_consecutive_failures})")
                
                # Check if we hit the daily swipe limit (vote quota)
                try:
                    blocker_elem = browser.find_element(By.CSS_SELECTOR, '.encounters-user__blocker, [data-qa-role="encounters-blocker-vote-quota"]')
                    if blocker_elem and blocker_elem.is_displayed():
                        # Check for the specific limit message
                        try:
                            title_elem = blocker_elem.find_element(By.CSS_SELECTOR, '[data-qa-role="cta-box-title"], .cta-box__title')
                            title_text = title_elem.text.lower() if title_elem else ""
                            if 'end of the line' in title_text or 'hit the end' in title_text:
                                print(f"{CYAN} Daily swipe limit reached: 'You've hit the end of the line — for today!'")
                                print(f"{CYAN} Successfully extracted {profile_count} profile(s) before hitting limit")
                                daily_limit_hit = True
                                break
                        except:
                            # If we found the blocker element, it's likely the limit
                            print(f"{CYAN} Daily swipe limit detected (encounters-blocker-vote-quota)")
                            print(f"{CYAN} Successfully extracted {profile_count} profile(s) before hitting limit")
                            daily_limit_hit = True
                            break
                except NoSuchElementException:
                    pass  # Blocker not found, continue with other checks
                except Exception as e:
                    print(f"{YELLOW} Error checking for swipe limit: {e}")
                
                # Check if we hit the end (no more profiles)
                page_source = browser.page_source.lower()
                end_indicators = [
                    'no more profiles', 'out of people', 'no one new', 
                    'no one around', 'all caught up', 'see you tomorrow',
                    'come back tomorrow', 'no matches', 'empty state',
                    'end of the line', 'hit the end', 'vote quota',
                    'upgrade to bumble boost', 'wait until tomorrow'
                ]
                if any(indicator in page_source for indicator in end_indicators):
                    # Check if it's a daily limit (vote quota, end of the line)
                    if any(indicator in page_source for indicator in ['end of the line', 'hit the end', 'vote quota', 'wait until tomorrow']):
                        daily_limit_hit = True
                        print(f"{CYAN} Daily limit detected in page content")
                    print(f"{CYAN} No more profiles available (detected end state)")
                    if profile_count > 0:
                        print(f"{CYAN} Successfully extracted {profile_count} profile(s) before stopping")
                    break
                
                # Check URL for empty state indicators
                current_url = browser.current_url.lower()
                if 'empty' in current_url or 'out-of-people' in current_url:
                    print(f"{CYAN} No more profiles available (detected in URL)")
                    if profile_count > 0:
                        print(f"{CYAN} Successfully extracted {profile_count} profile(s) before stopping")
                    break
                
                # Stop after max consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    print(f"{YELLOW} Stopping after {max_consecutive_failures} consecutive failures to extract profile")
                    if profile_count > 0:
                        print(f"{CYAN} Successfully extracted {profile_count} profile(s) before stopping")
                    break
                
                # Try handling match popup or continue button
                if handle_match_popup(browser):
                    time.sleep(2)
                    consecutive_failures = 0  # Reset counter if popup was handled
                    continue
                
                # If extraction failed, try to swipe/click to move to next profile
                # This prevents getting stuck on the same profile
                if not no_swipe:
                    print(f"{CYAN} Extraction failed - attempting to swipe/click to move to next profile...")
                    swipe_success = swipe_right(browser)
                    if not swipe_success:
                        # Try clicking continue button as fallback
                        handle_match_popup(browser)
                    time.sleep(delay)
                else:
                    # In no-swipe mode, we can't move forward, so break
                    print(f"{CYAN} No-swipe mode: Cannot move to next profile without swiping")
                    break
                
                # Wait a bit before trying next profile
                time.sleep(2)
                continue
            
            # Reset failure counter on successful extraction
            consecutive_failures = 0
            
            # Profile data should now always have a name (either extracted or placeholder)
            # Save profile data (name should be present at this point)
            if profile_data and profile_data.get("name"):
                # STEP 1: Save to JSON immediately (backup) - ALWAYS do this first
                json_saved = False
                if json_backup_file:
                    json_saved = save_profile_to_json(profile_data, json_backup_file)
                    if json_saved:
                        name_display = profile_data.get('name', 'Unknown')
                        if profile_data.get("_name_placeholder"):
                            print(f"{CYAN} 💾 Saved to JSON backup (placeholder name): {name_display} ({profile_data.get('age', '?')})")
                        else:
                            print(f"{CYAN} 💾 Saved to JSON backup: {name_display} ({profile_data.get('age', '?')})")
                    else:
                        print(f"{RED} ❌ Failed to save {profile_data.get('name', 'Unknown')} to JSON backup")
                
                # STEP 2: Save to Notion if enabled (after JSON backup)
                notion_saved = False
                if save_to_notion:
                    notion_saved = save_profile_to_notion(profile_data)
                    # Note: save_profile_to_notion already prints status messages
                
                # Always add to list for final JSON save (redundancy)
                all_profiles.append(profile_data)
                profile_count += 1
                
                if not save_to_notion and not json_backup_file:
                    # Only print extraction message if neither Notion nor JSON backup is enabled
                    name_display = profile_data.get('name', 'Unknown')
                    if profile_data.get("_name_placeholder"):
                        print(f"{GREEN} Extracted (placeholder name): {name_display} ({profile_data.get('age', '?')})")
                    else:
                        print(f"{GREEN} Extracted: {name_display} ({profile_data.get('age', '?')})")
            else:
                print(f"{RED} ERROR: Profile data is None or missing name - this should not happen after placeholder generation")
                consecutive_failures += 1
                # Don't add incomplete profiles to the list
                # Swipe/click to move to next profile instead of retrying the same one
                if not no_swipe:
                    print(f"{CYAN} Attempting to swipe/click to move to next profile...")
                    swipe_success = swipe_right(browser)
                    if not swipe_success:
                        # Try clicking continue button as fallback
                        handle_match_popup(browser)
                    time.sleep(delay)
                else:
                    # In no-swipe mode, we can't move forward, so break
                    print(f"{CYAN} No-swipe mode: Cannot move to next profile without swiping")
                    break
                
                # Stop if we've hit max consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    print(f"{YELLOW} Stopping after {max_consecutive_failures} consecutive failures to extract profile")
                    if profile_count > 0:
                        print(f"{CYAN} Successfully extracted {profile_count} profile(s) before stopping")
                    break
                
                continue
            
            # Swipe right after extraction (unless --no-swipe is set)
            if no_swipe:
                # In no-swipe mode, we can't see the next profile without swiping
                # So we break after extracting the current profile
                print(f"{CYAN} No-swipe mode: Extracted profile {profile_count}, stopping (cannot see next profile without swiping)")
                break
            else:
                # Swipe right to see next profile
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
            if daily_limit_hit:
                print(f"{CYAN} Daily limit reached before extracting any profiles - exiting gracefully")
                sys.exit(0)
            else:
                print(f"{RED} Error: No profiles extracted")
                sys.exit(1)
        
        print(f"{GREEN} Successfully extracted {len(all_profiles)} profile(s)")
        
        # Final JSON save (redundancy check - profiles should already be saved incrementally)
        # This ensures we have a complete file even if incremental saves failed
        if output_format == 'json':
            # Use the backup file if it exists, otherwise generate a new one
            final_json_file = json_backup_file if json_backup_file else output_file
            if not final_json_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                suffix = '_backup' if save_to_notion else ''
                final_json_file = f"bumble_profiles_{timestamp}{suffix}.json"
            
            # Final save to ensure completeness
            try:
                with open(final_json_file, 'w', encoding='utf-8') as f:
                    json.dump(all_profiles, f, indent=2, ensure_ascii=False)
                print(f"{GREEN} Final JSON backup saved: {final_json_file} ({len(all_profiles)} profiles)")
            except Exception as e:
                print(f"{YELLOW} Warning: Could not save final JSON backup: {e}")
            
            output_file = final_json_file
        else:  # CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                if all_profiles:
                    fieldnames = [
                        'extracted_at', 'name', 'age', 'bio', 'job', 'education', 
                        'location', 'from_location', 'preferences', 'badges', 
                        'question_answers', 'spotify_artists', 'image_urls'
                    ]
                    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                    writer.writeheader()
                    for profile in all_profiles:
                        # Convert lists/dicts to strings for CSV
                        row = profile.copy()
                        if 'image_urls' in row and isinstance(row['image_urls'], list):
                            row['image_urls'] = '; '.join(row['image_urls'])
                        if 'badges' in row and isinstance(row['badges'], list):
                            row['badges'] = '; '.join(row['badges'])
                        if 'spotify_artists' in row and isinstance(row['spotify_artists'], list):
                            row['spotify_artists'] = '; '.join(row['spotify_artists'])
                        if 'question_answers' in row and isinstance(row['question_answers'], dict):
                            # Convert dict to string format: "Q1: A1 | Q2: A2"
                            qa_pairs = [f"{q}: {a}" for q, a in row['question_answers'].items()]
                            row['question_answers'] = ' | '.join(qa_pairs)
                        writer.writerow(row)
        
        if output_format == 'json':
            print(f"{GREEN} JSON backup file: {output_file}")
        else:
            print(f"{GREEN} Data saved to: {output_file}")
        
        if save_to_notion:
            print(f"{CYAN} Summary: {len(all_profiles)} profile(s) extracted, saved to JSON backup, and synced to Notion")
        else:
            print(f"{CYAN} Summary: {len(all_profiles)} profile(s) extracted and saved to JSON")
        
        if no_swipe:
            print(f"{CYAN} Mode: Extract only (no swiping)")
        else:
            print(f"{CYAN} Mode: Extract and swipe right")
        
    except KeyboardInterrupt:
        print(f"\n{YELLOW} Interrupted by user")
        if all_profiles:
            print(f"{CYAN} Saving {len(all_profiles)} profile(s) extracted so far...")
            # Use existing JSON backup file if available, otherwise create partial file
            if output_format == 'json':
                partial_file = json_backup_file if json_backup_file else None
                if not partial_file:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    partial_file = f"bumble_profiles_{timestamp}_partial.json"
                # Final save of all profiles to ensure completeness
                try:
                    with open(partial_file, 'w', encoding='utf-8') as f:
                        json.dump(all_profiles, f, indent=2, ensure_ascii=False)
                    print(f"{GREEN} Partial JSON backup saved: {partial_file} ({len(all_profiles)} profiles)")
                except Exception as e:
                    print(f"{YELLOW} Warning: Could not save partial JSON backup: {e}")
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
            if keep_browser_open:
                print(f"{CYAN} Keeping browser open for debugging (use --keep-browser-open to auto-close)")
                print(f"{CYAN} Browser will remain open. Press Ctrl+C or close manually when done.")
                try:
                    # Wait indefinitely until user closes or interrupts
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print(f"\n{CYAN} Closing browser...")
                    browser.quit()
            else:
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
    parser.add_argument('--no-swipe', dest='no_swipe', action='store_true', default=False,
                        help='Extract profile data without swiping (useful for testing/inspection)')
    parser.add_argument('--keep-browser-open', dest='keep_browser_open', action='store_true', default=False,
                        help='Keep browser open after scraping completes (useful for debugging)')
    parser.add_argument('--save-to-notion', dest='save_to_notion', action='store_true', default=False,
                        help='Save each profile directly to Notion with retry logic (fallback to JSON if fails)')
    parser.add_argument('--gender', type=str, default=None,
                        help='Set gender for all scraped profiles (e.g., "female", "male", "non-binary")')
    
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
        location=args.location,
        no_swipe=args.no_swipe,
        keep_browser_open=args.keep_browser_open,
        save_to_notion=args.save_to_notion,
        gender=args.gender
    )


if __name__ == '__main__':
    main()


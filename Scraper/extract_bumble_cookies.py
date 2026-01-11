#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bumble Cookie Extractor
Automatically extracts Bumble cookies from browser cookie databases
Supports Firefox, Chrome, and Edge browsers
Similar to Tinder extract_tinder_cookies.py
"""

from argparse import ArgumentParser
from glob import glob
from os.path import expanduser, exists
from platform import system
from sqlite3 import OperationalError, connect
import json
import sys

# Color output (simple ASCII for cross-platform compatibility)
GREEN = "[OK]"
RED = "[X]"
YELLOW = "[!]"
CYAN = "[*]"


def has_bumble_cookies(cookiefile, is_firefox=True):
    """Check if a cookie file contains Bumble cookies."""
    try:
        if is_firefox:
            conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
            try:
                # Try modern Firefox cookie schema first - check for Bumble cookies
                result = conn.execute(
                    "SELECT COUNT(*) FROM moz_cookies WHERE baseDomain='bumble.com' OR baseDomain='.bumble.com'"
                ).fetchone()
                if result and result[0] > 0:
                    return True
            except OperationalError:
                # Fallback to host-based query
                result = conn.execute(
                    "SELECT COUNT(*) FROM moz_cookies WHERE host LIKE '%bumble.com'"
                ).fetchone()
                if result and result[0] > 0:
                    return True
        else:
            # Chrome/Edge cookie schema
            conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
            result = conn.execute(
                "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%bumble.com'"
            ).fetchone()
            if result and result[0] > 0:
                return True
        conn.close()
    except Exception:
        # Silently fail - don't print warnings during discovery
        pass
    return False


def get_firefox_cookie_files():
    """Get Firefox cookie files, checking both regular Firefox and Firefox Developer Edition."""
    platform = system()
    
    # Define all possible Firefox profile locations
    if platform == "Windows":
        cookie_patterns = [
            "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
            "~/AppData/Roaming/Mozilla/Firefox Developer Edition/Profiles/*/cookies.sqlite",
        ]
    elif platform == "Darwin":  # macOS
        cookie_patterns = [
            "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
            "~/Library/Application Support/Firefox Developer Edition/Profiles/*/cookies.sqlite",
        ]
    else:  # Linux
        cookie_patterns = [
            "~/.mozilla/firefox/*/cookies.sqlite",
            "~/.mozilla/firefox-developer-edition/*/cookies.sqlite",
        ]
    
    # Collect all cookie files from all locations
    all_cookiefiles = []
    for pattern in cookie_patterns:
        found_files = glob(expanduser(pattern))
        all_cookiefiles.extend(found_files)
    
    if not all_cookiefiles:
        return []
    
    # Prioritize cookie files that contain Bumble cookies
    prioritized = []
    others = []
    
    for cookiefile in all_cookiefiles:
        if has_bumble_cookies(cookiefile, is_firefox=True):
            prioritized.append(cookiefile)
        else:
            others.append(cookiefile)
    
    return prioritized + others


def get_chrome_cookie_files():
    """Get Chrome cookie files from all profile directories."""
    platform = system()
    
    if platform == "Windows":
        base_paths = [
            "~/AppData/Local/Google/Chrome/User Data",
        ]
    elif platform == "Darwin":  # macOS
        base_paths = [
            "~/Library/Application Support/Google/Chrome",
        ]
    else:  # Linux
        base_paths = [
            "~/.config/google-chrome",
        ]
    
    cookie_files = []
    for base_path in base_paths:
        expanded_base = expanduser(base_path)
        if not exists(expanded_base):
            continue
        
        # Check Default profile first
        default_cookies = expanduser(f"{base_path}/Default/Cookies")
        if exists(default_cookies):
            cookie_files.append(default_cookies)
        
        # Check other profiles
        profile_pattern = expanduser(f"{base_path}/Profile */Cookies")
        cookie_files.extend(glob(profile_pattern))
        
        # Also check numbered profiles
        numbered_pattern = expanduser(f"{base_path}/Profile [0-9]*/Cookies")
        cookie_files.extend(glob(numbered_pattern))
    
    # Prioritize cookie files that contain Bumble cookies
    prioritized = []
    others = []
    
    for cookiefile in cookie_files:
        if has_bumble_cookies(cookiefile, is_firefox=False):
            prioritized.append(cookiefile)
        else:
            others.append(cookiefile)
    
    return prioritized + others


def get_edge_cookie_files():
    """Get Edge cookie files from all profile directories."""
    platform = system()
    
    if platform == "Windows":
        base_paths = [
            "~/AppData/Local/Microsoft/Edge/User Data",
        ]
    elif platform == "Darwin":  # macOS
        base_paths = [
            "~/Library/Application Support/Microsoft Edge",
        ]
    else:  # Linux
        base_paths = [
            "~/.config/microsoft-edge",
        ]
    
    cookie_files = []
    for base_path in base_paths:
        expanded_base = expanduser(base_path)
        if not exists(expanded_base):
            continue
        
        # Check Default profile first
        default_cookies = expanduser(f"{base_path}/Default/Cookies")
        if exists(default_cookies):
            cookie_files.append(default_cookies)
        
        # Check other profiles
        profile_pattern = expanduser(f"{base_path}/Profile */Cookies")
        cookie_files.extend(glob(profile_pattern))
        
        # Also check numbered profiles
        numbered_pattern = expanduser(f"{base_path}/Profile [0-9]*/Cookies")
        cookie_files.extend(glob(numbered_pattern))
    
    # Prioritize cookie files that contain Bumble cookies
    prioritized = []
    others = []
    
    for cookiefile in cookie_files:
        if has_bumble_cookies(cookiefile, is_firefox=False):
            prioritized.append(cookiefile)
        else:
            others.append(cookiefile)
    
    return prioritized + others


def extract_cookies_from_firefox(cookiefile):
    """Extract Bumble cookies from Firefox cookie database."""
    try:
        conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
        
        # Try multiple query strategies
        queries = [
            # Try baseDomain first (modern Firefox schema)
            "SELECT name, value, host, path, expiry, isSecure, isHttpOnly FROM moz_cookies WHERE (baseDomain='bumble.com' OR baseDomain='.bumble.com')",
            # Fallback to host-based query
            "SELECT name, value, host, path, expiry, isSecure, isHttpOnly FROM moz_cookies WHERE (host='bumble.com' OR host='.bumble.com' OR host='www.bumble.com' OR host LIKE '%.bumble.com')",
            # Try with any Bumble domain
            "SELECT name, value, host, path, expiry, isSecure, isHttpOnly FROM moz_cookies WHERE host LIKE '%bumble.com'",
        ]
        
        for query in queries:
            try:
                cursor = conn.execute(query)
                rows = cursor.fetchall()
                
                if rows:
                    cookies = []
                    for row in rows:
                        cookie = {
                            'name': row[0],
                            'value': row[1],
                            'domain': row[2] if row[2].startswith('.') else f".{row[2]}" if not row[2].startswith('.') and '.' in row[2] else row[2],
                            'path': row[3] or '/',
                            'expiry': row[4] if row[4] else None,
                            'secure': bool(row[5]) if row[5] is not None else True,
                            'httpOnly': bool(row[6]) if row[6] is not None else False,
                        }
                        cookies.append(cookie)
                    
                    conn.close()
                    return cookies
            except OperationalError:
                continue
        
        conn.close()
        
    except Exception as e:
        print(f"{YELLOW} Warning: Could not extract from Firefox {cookiefile}: {e}")
    return None


def extract_cookies_from_chrome_edge(cookiefile):
    """Extract Bumble cookies from Chrome/Edge cookie database."""
    try:
        # Try read-only access first
        conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
        
        queries = [
            "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly FROM cookies WHERE host_key LIKE '%bumble.com'",
            "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly FROM cookies WHERE host_key LIKE '%.bumble.com'",
            "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly FROM cookies WHERE host_key='www.bumble.com'",
        ]
        
        for query in queries:
            try:
                cursor = conn.execute(query)
                rows = cursor.fetchall()
                
                if rows:
                    cookies = []
                    for row in rows:
                        host_key = row[2]
                        # Chrome/Edge uses host_key directly (no dot prefix needed)
                        domain = host_key if host_key.startswith('.') else f".{host_key}" if '.' in host_key else host_key
                        
                        # Handle encrypted values (Chrome/Edge may encrypt on Windows/macOS)
                        cookie_value = row[1]
                        if isinstance(cookie_value, bytes):
                            try:
                                cookie_value = cookie_value.decode('utf-8')
                            except UnicodeDecodeError:
                                # Value is encrypted, skip this cookie
                                continue
                        
                        cookie = {
                            'name': row[0],
                            'value': cookie_value,
                            'domain': domain,
                            'path': row[3] or '/',
                            'expiry': row[4] if row[4] else None,
                            'secure': bool(row[5]) if row[5] is not None else True,
                            'httpOnly': bool(row[6]) if row[6] is not None else False,
                        }
                        cookies.append(cookie)
                    
                    conn.close()
                    return cookies
            except OperationalError:
                continue
            except Exception:
                continue
        
        conn.close()
        
    except Exception as e:
        print(f"{YELLOW} Warning: Could not extract from Chrome/Edge {cookiefile}: {e}")
    return None


def extract_bumble_cookies(browser=None, output_file='bumble_cookies.json', quiet=False):
    """
    Extract Bumble cookies from browser cookie databases.
    
    Args:
        browser: Preferred browser ('firefox', 'chrome', 'edge') or None to try all
        output_file: Output file path for cookies JSON
        quiet: Suppress verbose output
    """
    if not quiet:
        print(f"{CYAN} Extracting Bumble cookies from browser...")
    
    cookies = None
    found_in_browser = None
    
    # Try Firefox
    if not browser or browser.lower() == 'firefox':
        if not quiet:
            print(f"{CYAN} Trying Firefox...")
        firefox_files = get_firefox_cookie_files()
        if firefox_files:
            if not quiet:
                print(f"{CYAN} Found {len(firefox_files)} Firefox profile(s)")
            for cookiefile in firefox_files:
                if not quiet:
                    print(f"{CYAN} Checking {cookiefile}...")
                cookies = extract_cookies_from_firefox(cookiefile)
                if cookies:
                    if not quiet:
                        print(f"{GREEN} Found {len(cookies)} Bumble cookies in Firefox: {cookiefile}")
                    found_in_browser = 'Firefox'
                    break
        else:
            if not quiet:
                print(f"{YELLOW} No Firefox cookie files found")
    
    # Try Chrome
    if not cookies and (not browser or browser.lower() == 'chrome'):
        if not quiet:
            print(f"{CYAN} Trying Chrome...")
        chrome_files = get_chrome_cookie_files()
        if chrome_files:
            if not quiet:
                print(f"{CYAN} Found {len(chrome_files)} Chrome profile(s)")
            for cookiefile in chrome_files:
                if not quiet:
                    print(f"{CYAN} Checking {cookiefile}...")
                # Check if browser is locked (Windows/macOS Chrome locks Cookies database)
                try:
                    cookies = extract_cookies_from_chrome_edge(cookiefile)
                    if cookies:
                        if not quiet:
                            print(f"{GREEN} Found {len(cookies)} Bumble cookies in Chrome: {cookiefile}")
                        found_in_browser = 'Chrome'
                        break
                except Exception as e:
                    if 'database is locked' in str(e).lower() or 'locked' in str(e).lower():
                        if not quiet:
                            print(f"{YELLOW} Chrome cookie database is locked. Close Chrome and try again.")
                    else:
                        if not quiet:
                            print(f"{YELLOW} Warning: Could not read Chrome cookies: {e}")
        else:
            if not quiet:
                print(f"{YELLOW} No Chrome cookie files found")
    
    # Try Edge
    if not cookies and (not browser or browser.lower() == 'edge'):
        if not quiet:
            print(f"{CYAN} Trying Edge...")
        edge_files = get_edge_cookie_files()
        if edge_files:
            if not quiet:
                print(f"{CYAN} Found {len(edge_files)} Edge profile(s)")
            for cookiefile in edge_files:
                if not quiet:
                    print(f"{CYAN} Checking {cookiefile}...")
                try:
                    cookies = extract_cookies_from_chrome_edge(cookiefile)
                    if cookies:
                        if not quiet:
                            print(f"{GREEN} Found {len(cookies)} Bumble cookies in Edge: {cookiefile}")
                        found_in_browser = 'Edge'
                        break
                except Exception as e:
                    if 'database is locked' in str(e).lower() or 'locked' in str(e).lower():
                        if not quiet:
                            print(f"{YELLOW} Edge cookie database is locked. Close Edge and try again.")
                    else:
                        if not quiet:
                            print(f"{YELLOW} Warning: Could not read Edge cookies: {e}")
        else:
            if not quiet:
                print(f"{YELLOW} No Edge cookie files found")
    
    if not cookies:
        print(f"{RED} Error: Could not find Bumble cookies in any browser")
        print(f"{YELLOW} Make sure you are logged into Bumble in your browser")
        print(f"{YELLOW} If Bumble requires verification (CAPTCHA/puzzle), complete it manually first")
        print(f"{YELLOW} If your account is temporarily locked, wait for Bumble to unlock it before extracting cookies")
        print(f"{YELLOW} If using Chrome/Edge, try closing the browser first")
        print(f"{YELLOW} Or use Firefox for easier automatic extraction")
        sys.exit(1)
    
    # Check if we got authentication cookies or just load balancer cookies
    # Bumble uses 'session' as the main authentication cookie
    auth_cookie_names = ['session', 'BumbleID', 'sessionid', 'access_token', 'id_token', '__cf_bm', 'bumble_session']
    found_auth_cookies = any(c['name'] in auth_cookie_names for c in cookies)
    found_only_load_balancer = all(c['name'] in ['AWSALB', 'AWSALBCORS', 'g_state', '_ga', '_gid', 'dnsDisplayed', 'ccpaApplies', 'ccpaConsentAll'] for c in cookies)
    
    # Save cookies to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        
        if not quiet:
            print(f"{GREEN} Bumble cookies saved to: {output_file}")
            print(f"{GREEN} Total cookies extracted: {len(cookies)}")
            print(f"{CYAN} Cookie names: {', '.join([c['name'] for c in cookies[:10]])}{'...' if len(cookies) > 10 else ''}")
            
            if found_only_load_balancer:
                print(f"{YELLOW} Warning: Only load balancer/analytics cookies found (not authentication cookies)")
                print(f"{YELLOW} This may indicate:")
                print(f"{YELLOW}  1. You are not fully logged into Bumble in your browser")
                print(f"{YELLOW}  2. Bumble requires verification (CAPTCHA/puzzle) - complete it manually first")
                print(f"{YELLOW}  3. Your account is temporarily locked - wait for Bumble to unlock it")
                print(f"{YELLOW}  4. Try using email/password authentication as fallback: --email <email> --password <password>")
            elif not found_auth_cookies:
                print(f"{YELLOW} Note: Authentication cookies (BumbleID, sessionid, access_token) not found")
                print(f"{YELLOW} If login fails, you may need to complete manual verification in your browser")
        
        return output_file
    except Exception as e:
        print(f"{RED} Error: Failed to save cookies to {output_file}: {e}")
        sys.exit(1)


def main():
    parser = ArgumentParser(description='Extract Bumble cookies from browser cookie databases')
    parser.add_argument('--browser', choices=['firefox', 'chrome', 'edge'],
                        help='Preferred browser for cookie extraction (default: try all)')
    parser.add_argument('-o', '--output', default='bumble_cookies.json',
                        help='Output file path for cookies JSON (default: bumble_cookies.json)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress verbose output')
    
    args = parser.parse_args()
    
    extract_bumble_cookies(
        browser=args.browser,
        output_file=args.output,
        quiet=args.quiet
    )


if __name__ == '__main__':
    main()


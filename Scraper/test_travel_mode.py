#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify if Bumble Travel Mode works with web scraping.

This script:
1. Scrapes a small number of profiles
2. Extracts location data from each profile
3. Analyzes whether profiles match the Travel Mode location
4. Reports results to help determine if Travel Mode works or if VPN/proxy is needed
"""

import sys
import json
import argparse
from pathlib import Path
from collections import Counter

# Add parent directory to path to import scraper functions
sys.path.insert(0, str(Path(__file__).parent))

try:
    from bumble_profile_scraper import scrape_profiles
except ImportError:
    print("[X] Error: Could not import bumble_profile_scraper")
    print("[+] Make sure you're running this from the Scraper directory")
    sys.exit(1)


def analyze_locations(profiles_data, expected_city="Seattle"):
    """
    Analyze extracted profile locations to determine if Travel Mode is working.
    
    Args:
        profiles_data: List of profile dictionaries
        expected_city: City name expected from Travel Mode (default: Seattle)
    
    Returns:
        Dictionary with analysis results
    """
    if not profiles_data:
        return {
            "error": "No profiles to analyze",
            "total_profiles": 0
        }
    
    # Extract locations from profiles
    locations = []
    location_parts = []
    
    for profile in profiles_data:
        location = profile.get("location")
        if location:
            locations.append(location)
            # Try to extract city name from location string
            # Format is usually "City | ~X miles away" or "City, State"
            parts = location.split("|")
            if parts:
                city_part = parts[0].strip()
                location_parts.append(city_part)
    
    # Count location occurrences
    location_counter = Counter(location_parts)
    
    # Check if expected city appears in locations
    expected_city_lower = expected_city.lower()
    matching_locations = [
        loc for loc in location_parts 
        if expected_city_lower in loc.lower()
    ]
    
    # Calculate statistics
    total_profiles = len(profiles_data)
    profiles_with_location = len(location_parts)
    matching_count = len(matching_locations)
    match_percentage = (matching_count / profiles_with_location * 100) if profiles_with_location > 0 else 0
    
    # Determine if Travel Mode is working
    # If >50% of profiles are from expected city, Travel Mode likely works
    # If <20% are from expected city, Travel Mode likely doesn't work
    if match_percentage >= 50:
        status = "✅ LIKELY WORKING"
        recommendation = "Travel Mode appears to be working! You can use Premium + Travel Mode."
    elif match_percentage >= 20:
        status = "⚠️ PARTIALLY WORKING"
        recommendation = "Travel Mode may be partially working, but IP geolocation is still affecting results. Consider using VPN."
    else:
        status = "❌ NOT WORKING"
        recommendation = "Travel Mode is not working with web scraping. Use VPN or proxy instead."
    
    return {
        "status": status,
        "total_profiles": total_profiles,
        "profiles_with_location": profiles_with_location,
        "matching_count": matching_count,
        "match_percentage": round(match_percentage, 1),
        "expected_city": expected_city,
        "location_distribution": dict(location_counter.most_common(10)),
        "recommendation": recommendation,
        "all_locations": locations[:20]  # First 20 for reference
    }


def main():
    parser = argparse.ArgumentParser(
        description="Test if Bumble Travel Mode works with web scraping"
    )
    parser.add_argument(
        '--cookies',
        type=str,
        default=None,
        help='Path to cookie file (required)'
    )
    parser.add_argument(
        '--expected-city',
        type=str,
        default='Seattle',
        help='Expected city from Travel Mode (default: Seattle)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of profiles to scrape for testing (default: 10)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Run browser in non-headless mode for debugging'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file for test results (default: travel_mode_test_results.json)'
    )
    
    args = parser.parse_args()
    
    if not args.cookies:
        print("[X] Error: --cookies is required")
        print("[+] Usage: python test_travel_mode.py --cookies <cookie_file> [options]")
        sys.exit(1)
    
    print("[*] Testing Travel Mode compatibility with web scraping...")
    print(f"[*] Expected city: {args.expected_city}")
    print(f"[*] Scraping {args.limit} profiles for testing...")
    print()
    
    # Scrape profiles
    output_file = args.output or f"travel_mode_test_{args.expected_city.lower()}.json"
    
    try:
        profiles_data = scrape_profiles(
            cookie_file=args.cookies,
            limit=args.limit,
            delay=2.0,
            output_format='json',
            output_file=output_file,
            headless=not args.no_headless,
            location=None,  # Don't set location, let Travel Mode handle it
            no_swipe=True  # Don't swipe, just extract data
        )
        
        if not profiles_data:
            print("[X] Error: No profiles were scraped")
            print("[+] Check your cookies and ensure you're logged in")
            sys.exit(1)
        
        # Analyze results
        print("[*] Analyzing location data...")
        analysis = analyze_locations(profiles_data, args.expected_city)
        
        # Print results
        print()
        print("=" * 60)
        print("TRAVEL MODE TEST RESULTS")
        print("=" * 60)
        print(f"Status: {analysis['status']}")
        print(f"Total profiles scraped: {analysis['total_profiles']}")
        print(f"Profiles with location data: {analysis['profiles_with_location']}")
        print(f"Profiles from {args.expected_city}: {analysis['matching_count']} ({analysis['match_percentage']}%)")
        print()
        print("Location Distribution:")
        for location, count in analysis['location_distribution'].items():
            print(f"  - {location}: {count}")
        print()
        print("Recommendation:")
        print(f"  {analysis['recommendation']}")
        print("=" * 60)
        
        # Save detailed results
        results_file = output_file.replace('.json', '_analysis.json')
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                "test_config": {
                    "expected_city": args.expected_city,
                    "profiles_scraped": args.limit
                },
                "analysis": analysis,
                "profiles": profiles_data
            }, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Detailed results saved to: {results_file}")
        
        # Return exit code based on results
        if "NOT WORKING" in analysis['status']:
            sys.exit(1)  # Travel Mode not working
        elif "PARTIALLY WORKING" in analysis['status']:
            sys.exit(2)  # Partially working
        else:
            sys.exit(0)  # Working
        
    except Exception as e:
        print(f"[X] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


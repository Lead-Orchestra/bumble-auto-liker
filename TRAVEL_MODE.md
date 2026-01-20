# Bumble Travel Mode & Location Settings

## Overview

Bumble uses **IP-based geolocation** to determine which profiles to show you. This means your physical IP address location takes priority over browser geolocation settings.

## The Problem

- **"Lives in" location** in profile settings is just a profile field - it doesn't change which profiles you see
- **Search/matching location** is determined by your IP address
- Setting browser geolocation via Chrome DevTools Protocol doesn't override IP-based detection
- If your IP is in Denver, you'll see Denver profiles even if you set "Lives in" to Seattle

## Solutions

### 1. Bumble Premium Travel Mode ⭐ (Recommended for Manual Use)

**Travel Mode** allows you to change your location to anywhere in the world for 7 days. Your profile will show up as being in the city you choose.

**Features:**
- Set location to any city worldwide
- Profile shows as being in chosen city
- Lasts for 7 days
- Requires Bumble Premium subscription

**⚠️ CRITICAL LIMITATION:**
- **Travel Mode is NOT available on Bumble Web** (desktop browser)
- **Only available on Bumble mobile app** (iOS/Android)

**Implications for Web Scraping:**
- Cannot use Travel Mode directly with the web scraper
- However, you can:
  1. Set Travel Mode in the mobile app
  2. Extract cookies from the mobile app session (if possible)
  3. Use those cookies with the web scraper
  4. Note: This may not fully work as the web app may still use IP-based geolocation

## Mobile Travel Mode → Web Scraping Compatibility

### Key Finding

**Travel Mode is an account-level setting that persists across platforms**, BUT Bumble Web may still use IP-based geolocation as a fallback to determine which profiles to show you.

### What Works

- ✅ **Travel Mode set on mobile app persists to web app** (account-level setting)
- ✅ **Travel Mode lasts 7 days** and doesn't reset unless manually disabled
- ✅ **Cookies from mobile session can be used** with web scraper
- ✅ **Your profile will show as being in the Travel Mode city** on both mobile and web

### What Doesn't Work

- ❌ **Bumble Web may still prioritize IP-based geolocation** over Travel Mode
- ❌ **If your IP is in Denver, web scraper may still see Denver profiles** even with Travel Mode set to Seattle
- ❌ **Travel Mode location may only affect your profile visibility**, not which profiles YOU see
- ❌ **The profiles shown to you may still be based on your IP address**, regardless of Travel Mode setting

### Conclusion

**Travel Mode may not fully work for web scraping** because Bumble's backend likely uses IP geolocation to determine which profiles to show you, regardless of Travel Mode setting. However, it's worth testing since Travel Mode is included with Premium and costs nothing extra.

### Testing Travel Mode Compatibility

To determine if Travel Mode works with web scraping, use the automated test script:

#### Automated Testing (Recommended)

1. **Set Travel Mode on Mobile:**
   - Open Bumble mobile app
   - Go to Settings → Travel Mode
   - Set location to target city (e.g., Seattle)
   - Verify Travel Mode is active

2. **Run Test Script:**
   ```bash
   cd Scraper
   python test_travel_mode.py \
     --cookies ../bumble_cookies.json \
     --expected-city Seattle \
     --limit 10 \
     --no-headless
   ```

3. **Review Results:**
   - Script will analyze scraped profiles
   - Shows percentage of profiles from expected city
   - Provides recommendation based on results
   - Saves detailed analysis to JSON file

4. **Interpret Results:**
   - **>50% matching:** ✅ Travel Mode works! Use Premium + Travel Mode
   - **20-50% matching:** ⚠️ Partially working, consider VPN
   - **<20% matching:** ❌ Not working, use VPN or proxy

#### Manual Testing

1. **Set Travel Mode on Mobile:**
   - Open Bumble mobile app
   - Go to Settings → Travel Mode
   - Set location to target city (e.g., Seattle)
   - Verify Travel Mode is active

2. **Run Web Scraper:**
   ```bash
   pnpm scrape:bumble \
     --auto-session \
     --targeting-spec "1. Dating App Leads (Tinder & Bumble)" \
     --limit 10 \
     --no-swipe
   ```

3. **Check Results:**
   - Examine the `location` field in extracted profiles
   - If profiles are from Seattle: ✅ Travel Mode works!
   - If profiles are from Denver (your IP location): ❌ Travel Mode doesn't override IP geolocation

4. **Document Results:**
   - Record whether Travel Mode worked or not
   - This will help determine if you need VPN/proxy

### 2. VPN/Proxy (Most Reliable for Automated Scraping)

**Why it works:**
- Changes your actual IP address to the target location
- Bumble's backend sees requests from the target city's IP
- Most reliable method for automated scraping

**Implementation:**
- Use a VPN service with Seattle servers
- Or use a residential proxy service (Bright Data, Oxylabs, Smartproxy)
- Configure proxy in browser automation tool

### 3. Manual Location Refresh (Limited Effectiveness)

**How it works:**
1. Log into Bumble Web
2. Go to Settings → Location
3. Click the refresh icon next to city name
4. This triggers browser to "ping" current location

**Limitations:**
- Still relies on IP address
- May not override IP-based detection
- Requires manual intervention

## Bumble Premium Features

### Premium Includes:
- ✅ **Unlimited swipes** (no daily limit)
- ✅ **Travel Mode** (mobile app only - change location to any city)
- ✅ **Liked You** (see who liked you first)
- ✅ **Unlimited Advanced Filters** (height, education, exercise, etc.)
- ✅ **Backtrack** (undo accidental left swipes)
- ✅ **Unlimited Extends** (more time to message matches)
- ✅ **Rematch** (reconnect with expired matches)
- ✅ **One Spotlight per week** (boost visibility for 30 minutes)
- ✅ **Five SuperSwipes per week** (show extra interest)
- ✅ **Incognito Mode** (only seen by people you've liked)

### Premium+ Includes:
All Premium features, plus:
- ✅ **10 SuperSwipes per week** (instead of 5)
- ✅ **Two Compliments per week**
- ✅ **One Spotlight per week**
- ✅ **Profile insights** (see how your profile performs)

## Current Scraper Implementation

The scraper currently:
1. Attempts to set browser geolocation via Chrome DevTools Protocol
2. Tries to find and interact with location settings in Bumble Web UI
3. Warns that IP-based geolocation takes priority

**Known Limitations:**
- Cannot use Travel Mode (not available on web)
- Browser geolocation may not override IP detection
- Manual "Lives in" setting doesn't change matching location

## Cost Comparison Analysis

### Your Requirements
- High volume scraping (1000+ profiles/month)
- Need unlimited swipes (requires Bumble Premium)

### Option 1: Bumble Premium with Travel Mode
- **Cost:** ~$30-50/month (includes Travel Mode + unlimited swipes)
- **Pros:** 
  - Official feature, no ban risk
  - Includes unlimited swipes you need
  - No additional setup required
- **Cons:** 
  - May not work with web scraper (IP-based geolocation override)
  - Only available on mobile app
- **Best if:** Travel Mode actually works with web scraping (needs testing)

### Option 2: VPN + Bumble Premium
- **Cost:** ~$5-15/month (VPN) + $30-50/month (Premium) = **$35-65/month total**
- **Pros:** 
  - Reliable IP-based location change
  - Works with web scraper
  - Simple setup (system-wide VPN)
- **Cons:** 
  - More expensive than Premium alone
  - Requires VPN service subscription
- **Best if:** Travel Mode doesn't work with web scraping

### Option 3: Residential Proxy + Bumble Premium
- **Cost:** ~$0.49-7/GB (proxy) + $30-50/month (Premium)
- **For 1000 profiles/month:** ~50-200GB estimated = **$25-1400/month** (highly variable)
- **Pros:** 
  - Most reliable for scraping
  - Can rotate IPs per request
  - Harder to detect than datacenter proxies
- **Cons:** 
  - Can be very expensive at high volumes
  - Pay-per-GB pricing can be unpredictable
  - Requires proxy configuration in scraper
- **Best if:** You need IP rotation and have budget for high-volume scraping

**Recommended Providers:**
- **Evomi:** $0.49/GB residential proxies
- **IPRoyal:** ~$7/GB residential, flexible pay-as-you-go
- **Decodo (Smartproxy):** ~$0.50/GB datacenter plans
- **Webshare:** ~$0.01/GB datacenter (unmetered plans available)

### Option 4: Datacenter Proxy + Bumble Premium
- **Cost:** ~$0.01-0.30/GB (proxy) + $30-50/month (Premium)
- **For 1000 profiles/month:** ~50-200GB estimated = **$30-110/month**
- **Pros:** 
  - Cheaper than residential
  - Fixed monthly plans available
  - Good for budget-conscious users
- **Cons:** 
  - Higher detection risk
  - May get blocked by Bumble
  - Less reliable than residential
- **Best if:** Budget-conscious and willing to risk detection

### Cost Comparison Table

| Option | Monthly Cost | Reliability | Setup Complexity | Best For |
|--------|-------------|-------------|------------------|----------|
| **Premium + Travel Mode** | $30-50 | ⚠️ Unknown (needs testing) | ✅ Easy | If Travel Mode works |
| **Premium + VPN** | $35-65 | ✅ High | ✅ Easy | Most cost-effective reliable |
| **Premium + Residential Proxy** | $55-1450+ | ✅✅ Highest | ⚠️ Medium | High-volume scraping |
| **Premium + Datacenter Proxy** | $30-110 | ⚠️ Medium | ⚠️ Medium | Budget-conscious |

## Recommendations

### For High-Volume Scraping (1000+ profiles/month) + Need Premium:

1. **Try Travel Mode First (Free with Premium)** ⭐
   - Set Travel Mode to Seattle on mobile app
   - Test if web scraper sees Seattle profiles
   - If it works: **Best option** - $30-50/month total
   - If it doesn't: Move to Option 2

2. **If Travel Mode Doesn't Work: Use VPN** ⭐⭐
   - Get Bumble Premium ($30-50/month) + VPN ($5-15/month)
   - Total: **$35-65/month**
   - Most cost-effective reliable solution
   - Simpler than proxy configuration

3. **If VPN Doesn't Work: Use Residential Proxy**
   - Only if Bumble blocks VPN IPs
   - Use pay-per-GB residential proxy (Evomi: $0.49/GB)
   - Monitor usage to control costs
   - Consider fixed monthly plans if available

### For Manual Testing:
1. Use Bumble Premium Travel Mode in mobile app
2. Set location to target city (e.g., Seattle)
3. Extract cookies from mobile session (if possible)
4. Use cookies with web scraper
5. Test if profiles shown match Travel Mode location

### For Automated Scraping:
1. **First:** Test Travel Mode (free with Premium)
2. **If Travel Mode fails:** Use VPN/proxy with target city IP
3. **Alternative:** Accept that profiles will be based on your IP location

## References

- [Bumble Premium Features](https://bumble.com/premium)
- [Bumble Help: Travel Mode](https://bumble.com/help/travel-mode)
- [Bumble Help: Change Location](https://bumble.com/help/how-can-i-change-my-location)


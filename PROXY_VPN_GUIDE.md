# Proxy & VPN Setup Guide for Bumble Scraper

## Overview

This guide explains how to configure VPN or proxy services with the Bumble web scraper to change your location for profile scraping. Since Bumble uses IP-based geolocation, changing your IP address is the most reliable way to see profiles from a specific location.

## When to Use VPN/Proxy

- ✅ Travel Mode doesn't work with web scraping (IP-based geolocation override)
- ✅ You need to scrape profiles from a specific city
- ✅ Your IP address is in a different location than your target city
- ✅ You want reliable, automated location control

## VPN vs Proxy

### VPN (Virtual Private Network)
- **How it works:** Routes all your internet traffic through a remote server
- **Setup:** System-wide, affects all applications
- **Cost:** ~$5-15/month
- **Pros:** Simple setup, works with any application
- **Cons:** Affects all internet traffic, may slow down other apps

### Proxy
- **How it works:** Routes only specific requests (browser traffic) through a proxy server
- **Setup:** Application-specific, only affects browser/scraper
- **Cost:** ~$0.01-7/GB (varies by type)
- **Pros:** More control, doesn't affect other apps, can rotate IPs
- **Cons:** More complex setup, pay-per-GB can be expensive

## Recommended Providers

### VPN Providers

| Provider | Cost/Month | Best For |
|----------|-----------|----------|
| **NordVPN** | ~$12 | General purpose, good speeds |
| **ExpressVPN** | ~$13 | Fast speeds, reliable |
| **Surfshark** | ~$12 | Budget-friendly, unlimited devices |
| **ProtonVPN** | ~$10 | Privacy-focused, free tier available |

### Proxy Providers

#### Residential Proxies (Harder to Detect)

| Provider | Cost | Best For |
|----------|------|----------|
| **Evomi** | $0.49/GB | Budget residential proxies |
| **IPRoyal** | ~$7/GB | Flexible pay-as-you-go |
| **GeoNode** | ~$0.49/GB | High-volume scraping |
| **Bright Data** | ~$15/GB | Enterprise-grade, most reliable |

#### Datacenter Proxies (Cheaper, Higher Detection Risk)

| Provider | Cost | Best For |
|----------|------|----------|
| **Webshare** | ~$0.01/GB | Budget-conscious, unmetered plans |
| **Decodo (Smartproxy)** | ~$0.50/GB | Good balance of cost/quality |
| **Proxy-Cheap** | ~$0.30/IP | Fixed monthly plans |

## VPN Setup Instructions

### Step 1: Choose and Subscribe to VPN Service

1. Select a VPN provider (see recommendations above)
2. Subscribe to a plan with servers in your target city (e.g., Seattle)
3. Download and install the VPN client

### Step 2: Connect to Target City Server

1. Open VPN client
2. Select server in target city (e.g., Seattle, WA)
3. Connect to server
4. Verify your IP has changed (visit https://ipapi.co/json/)

### Step 3: Run Scraper

The scraper will automatically use the VPN's IP address:

```bash
# No special configuration needed - VPN affects all traffic
pnpm scrape:bumble --auto-session --targeting-spec "1. Dating App Leads (Tinder & Bumble)" --limit 10
```

### Step 4: Verify Location

Check the extracted profiles to confirm they're from the target city:

```bash
# Check the output JSON file
cat bumble_profiles_*.json | grep -i "location"
```

## Proxy Setup Instructions

### Step 1: Choose and Subscribe to Proxy Service

1. Select a proxy provider (see recommendations above)
2. Subscribe to a plan
3. Get your proxy credentials:
   - Proxy host/endpoint
   - Port
   - Username (if required)
   - Password (if required)

### Step 2: Configure Proxy in Scraper

The scraper uses `undetected-chromedriver` which supports proxy configuration via Chrome options.

#### Option A: Environment Variables

Set proxy via environment variables:

```bash
# Format: http://username:password@proxy-host:port
export PROXY_URL="http://user:pass@proxy.example.com:8080"

# Or for SOCKS5:
export PROXY_URL="socks5://user:pass@proxy.example.com:1080"

# Run scraper
pnpm scrape:bumble --auto-session --targeting-spec "1. Dating App Leads (Tinder & Bumble)" --limit 10
```

#### Option B: Modify Scraper Code

Update `bumble_profile_scraper.py` to add proxy support:

```python
def create_chrome_options():
    """Create Chrome options with proxy support"""
    options = uc.ChromeOptions()
    
    # Add proxy if provided
    proxy_url = os.environ.get('PROXY_URL')
    if proxy_url:
        options.add_argument(f'--proxy-server={proxy_url}')
        print(f"{CYAN} Using proxy: {proxy_url}")
    
    # ... rest of options ...
    return options
```

### Step 3: Test Proxy Connection

Before running the full scraper, test the proxy:

```python
# Test script
import requests

proxy_url = "http://user:pass@proxy.example.com:8080"
proxies = {
    'http': proxy_url,
    'https': proxy_url
}

response = requests.get('https://ipapi.co/json/', proxies=proxies)
print(response.json())
# Should show proxy IP location, not your real IP
```

### Step 4: Run Scraper with Proxy

```bash
# Set proxy URL
export PROXY_URL="http://user:pass@proxy.example.com:8080"

# Run scraper
pnpm scrape:bumble --auto-session --targeting-spec "1. Dating App Leads (Tinder & Bumble)" --limit 10
```

## Cost Analysis for High-Volume Scraping

### Scenario: 1000 profiles/month

**Estimated Data Usage:**
- ~50-200GB per 1000 profiles (varies by profile complexity)
- Depends on images loaded, page interactions, etc.

**Cost Breakdown:**

| Solution | Monthly Cost | Notes |
|----------|-------------|-------|
| **VPN + Premium** | $35-65 | Fixed cost, unlimited usage |
| **Residential Proxy + Premium** | $55-1450+ | Pay-per-GB, highly variable |
| **Datacenter Proxy + Premium** | $30-110 | Cheaper but higher detection risk |

**Recommendation:**
- **Low-Medium Volume (< 500 profiles/month):** VPN is most cost-effective
- **High Volume (500-1000 profiles/month):** VPN still recommended unless you need IP rotation
- **Very High Volume (1000+ profiles/month):** Consider fixed monthly proxy plans or monitor usage carefully

## Proxy Configuration Examples

### Evomi Residential Proxy

```bash
# Get credentials from Evomi dashboard
export PROXY_URL="http://username:password@gateway.evomi.com:8080"

# Run scraper
pnpm scrape:bumble --auto-session --targeting-spec "1. Dating App Leads (Tinder & Bumble)" --limit 10
```

### Webshare Datacenter Proxy

```bash
# Get credentials from Webshare dashboard
export PROXY_URL="http://username:password@rotating-residential.webshare.io:80"

# Run scraper
pnpm scrape:bumble --auto-session --targeting-spec "1. Dating App Leads (Tinder & Bumble)" --limit 10
```

### IPRoyal Residential Proxy

```bash
# Get credentials from IPRoyal dashboard
export PROXY_URL="http://username:password@gateway.iproyal.com:12321"

# Run scraper
pnpm scrape:bumble --auto-session --targeting-spec "1. Dating App Leads (Tinder & Bumble)" --limit 10
```

## Troubleshooting

### Proxy Not Working

1. **Check proxy credentials:** Verify username/password are correct
2. **Test proxy connection:** Use test script above
3. **Check proxy format:** Ensure URL format is correct
4. **Firewall issues:** Ensure proxy port isn't blocked

### VPN Not Working

1. **Verify IP changed:** Check https://ipapi.co/json/ after connecting
2. **Server location:** Ensure VPN server is in target city
3. **DNS issues:** Try flushing DNS cache
4. **Browser cache:** Clear browser cache and cookies

### Still Seeing Wrong Location

1. **IP geolocation delay:** Some services take time to update
2. **Bumble cache:** Bumble may cache your location
3. **Try different server:** Switch to different VPN/proxy server
4. **Clear cookies:** Delete Bumble cookies and re-authenticate

## Best Practices

1. **Test First:** Always test with a small number of profiles before full scraping
2. **Monitor Costs:** Track proxy usage to avoid unexpected bills
3. **Rotate IPs:** If using proxies, rotate IPs periodically to avoid detection
4. **Respect Rate Limits:** Don't scrape too aggressively, even with proxy
5. **Use Residential IPs:** For better reliability, prefer residential proxies over datacenter

## Security Considerations

- **Don't share credentials:** Keep proxy/VPN credentials secure
- **Use HTTPS:** Ensure proxy supports HTTPS connections
- **Check provider privacy:** Review provider's privacy policy
- **Avoid free proxies:** Free proxies are often unreliable and may log your traffic

## References

- [Evomi - Residential Proxies](https://evomi.com/)
- [Webshare - Fast & Affordable Proxies](https://www.webshare.io/)
- [Decodo (Smartproxy) - Proxies & Web Scraping API](https://decodo.com/)
- [IPRoyal - Flexible Proxy Solutions](https://iproyal.com/)


# bumble-auto-liker
This script is designed to automate the process of swiping right on all potential matches on Bumble.

## Usage

1. Login to your bumble account on your computer (preferably chrome browser).
2. Open dev tools by pressing F12 key or Ctrl + Shift + I and go to _Sources_ tab, then click on _overrides_ tab.
3. Click on _Select folder for overrides_, it will open file explorer, create a folder and name it "overrides", Clik _Select Folder_. It will prompt for permission, click _Allow_.
4. Go back to _page_ tab. go to the file: top/eu1.bumbcdn.com/i/aco/bumble.com/v2/-/moxie/dist/vendor.02753106c1c46d84c250.js, right click it and select _override content_.
5. Format the file by clicking _{ }_ icon. Ctrl + F to search "e.isTrusted". It should be found on line number 3168.
6. Replace that line with "return true;". Save the file and reload the page.
7. Go to console tab paste the contents of [bumbleAutoLiker.js](https://github.com/amitoj-singh/bumble-auto-liker/blob/main/bumbleAutoLiker.js) and hit enter.
9. Reload your page to stop the script.

## Location Settings & Travel Mode

**⚠️ IMPORTANT:** Bumble uses **IP-based geolocation** to determine which profiles you see. This means your physical IP address location takes priority over browser geolocation settings.

### The Problem
- **"Lives in" location** in profile settings is just a profile field - it doesn't change which profiles you see
- **Search/matching location** is determined by your IP address
- Setting browser geolocation doesn't override IP-based detection

### Quick Decision Guide

```
Do you need unlimited swipes?
├─ YES → Get Bumble Premium ($30-50/month)
│   ├─ Test Travel Mode first (free with Premium)
│   │   ├─ Works? → Use Travel Mode ✅ ($30-50/month total)
│   │   └─ Doesn't work? → Add VPN ($35-65/month total)
│   └─ Travel Mode not available? → Use VPN ($35-65/month total)
│
└─ NO → Use VPN only ($5-15/month)
    └─ Note: You'll have swipe limits without Premium
```

### Solutions

#### 1. Bumble Premium Travel Mode ⚠️ (Mobile App Only)
- **Travel Mode allows changing location to any city for 7 days**
- **CRITICAL LIMITATION: Travel Mode is NOT available on Bumble Web** (desktop browser)
- **Only available on Bumble mobile app** (iOS/Android)
- **May not work with web scraper** (IP-based geolocation may override)
- **Cost:** Included with Premium ($30-50/month)
- **Best if:** You need Premium anyway, and Travel Mode works with web scraping

#### 2. VPN (Recommended for Web Scraping)
- Changes your actual IP address to the target location
- Most reliable method for automated web scraping
- **Cost:** $5-15/month + Premium ($30-50/month) = **$35-65/month total**
- **Best if:** Travel Mode doesn't work or you don't need Premium
- See [PROXY_VPN_GUIDE.md](./PROXY_VPN_GUIDE.md) for setup instructions

#### 3. Proxy (For Advanced Users)
- More control, can rotate IPs per request
- **Cost:** $0.01-7/GB (highly variable, can be expensive)
- **Best if:** You need IP rotation or have specific proxy requirements
- See [PROXY_VPN_GUIDE.md](./PROXY_VPN_GUIDE.md) for setup instructions

### Cost Comparison

| Solution | Monthly Cost | Reliability | Setup |
|----------|-------------|-------------|-------|
| **Premium + Travel Mode** | $30-50 | ⚠️ Unknown | ✅ Easy |
| **Premium + VPN** | $35-65 | ✅ High | ✅ Easy |
| **Premium + Residential Proxy** | $55-1450+ | ✅✅ Highest | ⚠️ Medium |
| **Premium + Datacenter Proxy** | $30-110 | ⚠️ Medium | ⚠️ Medium |

**Recommendation:** Try Travel Mode first (free with Premium), then use VPN if it doesn't work.

For detailed information, see:
- [TRAVEL_MODE.md](./TRAVEL_MODE.md) - Complete Travel Mode analysis and testing
- [PROXY_VPN_GUIDE.md](./PROXY_VPN_GUIDE.md) - VPN/Proxy setup instructions

## Important Note

As the Bumble UI keeps changing from time to time, it is possible that this script may encounter issues or may not work as expected due to updates made by Tinder.

If you encounter any issues or face difficulties while executing this script, please don't hesitate to raise an issue in this repository. We are committed to maintaining and improving the script to ensure its functionality with the latest Tinder UI changes. Your feedback and bug reports are highly valuable to us.

We will make every effort to address reported issues and update the script promptly. Thank you for your understanding and cooperation.

Feel free to [open an issue](https://github.com/amitoj-singh/bumble-auto-liker/issues) if you encounter any problems.


## Disclaimer

Please use this script responsibly and in compliance with Bumble's terms of service. Automation tools can potentially violate Tinder's policies. The authors and contributors of this script are not responsible for any misuse or consequences resulting from the use of this software.

## License

This project is licensed under the GNU General Public License v3.0 License - see the [LICENSE.md](LICENSE.md) file for details.

## Contributing

Contributions and feature requests are welcome! If you'd like to contribute to this project, please follow instructions on [contributing](contributing.md).

# SMS Automation via Google Messages

Options for programmatically sending SMS from ChromeOS/Linux while keeping messages tied to your phone number.

## The Problem

Google Messages has no public API. Messages for Web (messages.google.com) uses a proprietary encrypted WebSocket protocol that isn't documented.

## Options

### Browser Automation (messages.google.com)

Automate the Messages for Web interface using Puppeteer, Playwright, or Selenium.

**Pros:**
- Uses your actual phone number
- Messages appear in your normal conversation history
- Works from any machine with browser access

**Cons:**
- Fragile - breaks when Google changes UI
- Requires keeping a browser session authenticated
- QR code re-auth needed periodically
- Google may detect/block automation
- Complex setup for headless operation

**Basic approach:**
```javascript
// Puppeteer example (conceptual)
const browser = await puppeteer.launch({ userDataDir: './messages-profile' });
const page = await browser.newPage();
await page.goto('https://messages.google.com/web/conversations');

// Wait for conversation list (assumes already paired)
await page.waitForSelector('mws-conversation-list-item');

// Find or start conversation, type message, send
// ... (UI selectors change frequently)
```

**Challenges:**
- Must maintain authenticated browser profile
- Selectors are obfuscated class names that change
- RCS vs SMS handling differs
- Group messages have different UI flow

### Alternative: KDE Connect (Recommended)

More reliable than browser automation. Install on Android phone and Linux.

```bash
# Install
sudo apt install kdeconnect

# Pair with phone (one-time)
kdeconnect-cli --pair -d <device-id>

# Send SMS
kdeconnect-cli --send-sms "Your message" --destination "+1234567890" -d <device-id>
```

### Alternative: ADB

If phone is accessible via USB or wireless ADB:

```bash
adb shell service call isms 7 i32 0 s16 "com.android.mms" \
  s16 "+1234567890" s16 "null" s16 "Your message" s16 "null" s16 "null"
```

### Alternative: Tasker + HTTP Endpoint

Create a REST API on your phone using Tasker that triggers SMS sends.

## Summary

| Method | Reliability | Setup Effort | Maintenance |
|--------|-------------|--------------|-------------|
| Browser automation | Low | High | High (UI changes) |
| KDE Connect | High | Low | Low |
| ADB | High | Medium | Low |
| Tasker | High | Medium | Low |

**Recommendation:** Use KDE Connect for reliability. Browser automation is a last resort when other methods aren't viable.

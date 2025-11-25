# How to Clear Cache and Fix Captcha Issue

The captcha box is still showing due to browser cache. Follow these steps:

## Steps to Fix:

1. **Stop the dev server** (Ctrl+C)

2. **Clear build cache:**
   ```bash
   rm -rf node_modules/.cache dist .webpack_cache
   ```

3. **Restart the dev server:**
   ```bash
   npm run serve
   ```

4. **In your browser:**
   - Open Developer Tools (F12)
   - Go to Application tab (Chrome) or Storage tab (Firefox)
   - Click "Clear storage" or "Clear site data"
   - Check all boxes and click "Clear site data"
   - OR use a hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)

5. **If still showing:**
   - Open in Incognito/Private window
   - Or unregister service worker:
     - In DevTools > Application > Service Workers
     - Click "Unregister"

## Verify the fix:

After clearing cache, the registration page should:
- ✅ NOT show any captcha input box
- ✅ Allow registration with just username and password
- ✅ Not require captcha for submission


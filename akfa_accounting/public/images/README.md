# App Icons Required

Please create the following app icons for the AKFA HR Mobile PWA:

## Required Files

1. **icon-192.png**
   - Size: 192x192 pixels
   - Format: PNG with transparency
   - Purpose: App icon, splash screen, shortcuts

2. **icon-512.png**
   - Size: 512x512 pixels
   - Format: PNG with transparency
   - Purpose: High-resolution app icon, splash screen

## Design Guidelines

- **Logo**: Use AKFA company logo or HR symbol
- **Background**: Purple gradient (#667eea to #764ba2) or solid purple
- **Shape**: Square with rounded corners (let the OS handle corner radius)
- **Padding**: Leave 10% padding around the logo
- **Colors**: Match the app theme (purple gradient)
- **Style**: Modern, clean, professional

## Quick Creation Options

### Option 1: Use Figma/Photoshop
1. Create 512x512 canvas
2. Add purple gradient background
3. Place AKFA logo in center (with 10% padding)
4. Export as PNG at 512x512
5. Resize to 192x192 for smaller icon

### Option 2: Use Online Icon Generator
1. Visit https://realfavicongenerator.net/
2. Upload a square AKFA logo
3. Configure settings for PWA
4. Download and extract icon-192.png and icon-512.png

### Option 3: Use Canva
1. Go to https://www.canva.com/
2. Create 512x512 design
3. Add purple gradient background
4. Add AKFA logo
5. Download as PNG
6. Resize for 192x192 version

## Temporary Placeholder

Until real icons are created, the app will use browser default icons.
The app will still work, but won't have a custom icon on home screen.

## Installation

After creating icons:
1. Place both PNG files in this directory
2. Run: `bench build --app akfa_accounting`
3. Run: `bench --site akfa.local clear-cache`
4. Refresh browser and reinstall PWA

---

**Note**: These icons are referenced in `/public/manifest.json`

# Quick Start Guide

Get up and running in 3 minutes! 🚀

## 1. Clone the Repository

```bash
git clone https://github.com/yourusername/image-extractor-skill.git
cd image-extractor-skill
```

## 2. Install Dependencies

```bash
npm install
```

This installs all required packages:
- `axios` - for HTTP downloads
- `cheerio` - for HTML parsing
- `sharp` - for image metadata
- `fs-extra` - for file operations
- `prompt-sync` - for CLI input

## 3. Run the Skill

```bash
npm start
```

## 4. Follow the Prompts

```
Enter search topic: mountain landscape
[Select aspect ratio: 1 for 16:9, 2 for 9:16, or 3 for both]
[Enter minimum size or press Enter to skip]
```

## 5. Find Your Images

```
~/ImageExtractor/mountain-landscape/
```

## Example Session

```bash
$ npm start

╔════════════════════════════════════════╗
║   Google Image Extractor - Claude Skill   ║
╚════════════════════════════════════════╝

Enter search topic (e.g., "mountain landscape"): sunset ocean waves
✅ Base directory initialized: /Users/you/ImageExtractor

Aspect Ratio Options:
  1) 16:9 (Landscape/Wide)
  2) 9:16 (Portrait/Tall)
  3) Both

Select aspect ratio (1-3): 3
Enter minimum image size (e.g., "800x600" or press Enter for no minimum): 1920x1080

🔍 Starting image extraction...

📁 Topic folder created: /Users/you/ImageExtractor/sunset-ocean-waves
🔎 Scraping Google Images for "sunset ocean waves"...
📸 Found 20 potential images, validating...

⬇️  Downloading: https://example.com/image1.jpg
✅ Saved: image_1_1920x1080_16-9_1234567890.jpg (1920x1080)

⬇️  Downloading: https://example.com/image2.jpg
✅ Saved: image_2_1920x1080_16-9_1234567891.jpg (1920x1080)

⬇️  Downloading: https://example.com/image3.jpg
✅ Saved: image_3_2560x1440_16-9_1234567892.jpg (2560x1440)

⬇️  Downloading: https://example.com/image4.jpg
✅ Saved: image_4_1920x1080_9-16_1234567893.jpg (1920x1080)

⬇️  Downloading: https://example.com/image5.jpg
✅ Saved: image_5_1440x1920_9-16_1234567894.jpg (1440x1920)

╔════════════════════════════════════════╗
║              RESULTS                   ║
╚════════════════════════════════════════╝

✅ Downloaded: 5 images
⏭️  Skipped (duplicates): 0
❌ Failed: 0
📁 Saved to: /Users/you/ImageExtractor/sunset-ocean-waves

Downloaded images:
  1. image_1_1920x1080_16-9_1234567890.jpg
  2. image_2_1920x1080_16-9_1234567891.jpg
  3. image_3_2560x1440_16-9_1234567892.jpg
  4. image_4_1920x1080_9-16_1234567893.jpg
  5. image_5_1440x1920_9-16_1234567894.jpg

✨ Image extraction complete!
```

## Common Tasks

### Search for Landscapes Only (16:9)
```
Topic: beautiful landscapes
Aspect Ratio: 1 (16:9)
Min Size: 1920x1080
```

### Search for Portrait Phone Wallpapers (9:16)
```
Topic: dark aesthetic wallpaper
Aspect Ratio: 2 (9:16)
Min Size: 1440x2560
```

### No Size Restrictions
```
Topic: abstract art
Aspect Ratio: 3 (Both)
Min Size: [press Enter to skip]
```

## Where Are My Images?

All downloaded images go to:
```
~/ImageExtractor/
```

Each topic gets its own folder:
```
~/ImageExtractor/
├── mountain-landscape/
├── sunset-ocean-waves/
├── abstract-art/
└── beautiful-landscapes/
```

## Troubleshooting

### "No images found"
- Try a simpler search term
- Check your internet connection
- Google may be rate-limiting; wait 5 minutes and try again

### "npm command not found"
- Install Node.js from https://nodejs.org
- Restart your terminal

### Can't find ImageExtractor folder
- The folder is in your home directory
- macOS/Linux: `~/ImageExtractor/` or `/Users/yourname/ImageExtractor/`
- Windows: `C:\Users\YourName\ImageExtractor\`

### Images are wrong aspect ratio
- The validator has 10% tolerance (default)
- Try increasing tolerance in `src/AspectRatioValidator.js`

## Next Steps

1. **Explore the code:** Check `src/` folder to understand modules
2. **Customize settings:** Edit configuration in individual files
3. **Extend features:** Add multiple source support, batch processing, etc.
4. **Deploy:** Use with Claude Code or integrate into CI/CD

## Support

- Read the full [README.md](./README.md)
- Check [CHANGELOG.md](./CHANGELOG.md) for latest updates
- Open an issue on GitHub for bugs or features

---

Happy image hunting! 🎨📸

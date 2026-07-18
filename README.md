# 🖼️ Image Extractor — Claude Code Custom Skill

A custom skill for **Claude Code** that searches Google Images for any topic and
downloads 5 images directly to your local filesystem — with aspect ratio filtering
and duplicate detection built in.

---

## ✨ Features

| Feature | Details |
|--------|---------|
| 🔍 Google Image Search | Searches Google Images for any topic |
| 📁 Auto Folder Creation | Creates `~/Pictures/ImageExtractor/{topic}/` automatically |
| 📐 Aspect Ratio Filter | Choose `9:16` (portrait) or `16:9` (landscape) |
| 🚫 Duplicate Detection | MD5 hash comparison prevents saving the same image twice |
| 📦 5 Images Per Topic | Fetches up to 25 candidates to find 5 valid matches |
| 🔁 Re-run Safe | Re-running skips already-downloaded images |

---

## 📂 Repository Structure

```
image-extractor-skill/
├── SKILL.md                    ← Claude Code skill definition
├── README.md                   ← This file
├── scripts/
│   └── download_images.py      ← Core downloader (auto-installs deps)
└── references/
    └── setup.md                ← Manual setup & troubleshooting guide
```

---

## 🚀 Installation (Claude Code)

1. Clone this repo:
   ```bash
   git clone https://github.com/YOUR_USERNAME/image-extractor-skill.git
   ```

2. Add the skill to your Claude Code config:
   ```json
   {
     "skills": [
       "/path/to/image-extractor-skill"
     ]
   }
   ```

3. Restart Claude Code — the skill is now active.

---

## 💬 How to Use

Just talk to Claude Code naturally:

```
"Download 5 landscape images of northern lights"
"Get me portrait photos of lions in the savanna"
"Fetch 9:16 images of Tokyo street photography"
"Search for images of alpine meadows in 16:9"
```

Claude will:
1. Ask for the topic and ratio if not provided
2. Run the downloader script automatically
3. Report the saved folder path and results

---

## 📁 Output Structure

```
~/Pictures/ImageExtractor/
└── northern_lights/
    ├── image_1.jpg
    ├── image_2.jpg
    ├── image_3.jpg
    ├── image_4.jpg
    ├── image_5.jpg
    └── metadata.json
```

---

## ⚙️ Manual Script Usage

You can also run the script directly without Claude Code:

```bash
python3 scripts/download_images.py --topic "northern lights" --ratio "16:9"
python3 scripts/download_images.py --topic "city skyline" --ratio "9:16"
```

---

## 📦 Dependencies

Auto-installed on first run:
- `requests`
- `Pillow`
- `icrawler`

Or install manually:
```bash
pip install requests Pillow icrawler
```

---

## 📋 Requirements

- Python 3.8+
- Claude Code with custom skills enabled
- Internet connection

---

## 🛠️ Troubleshooting

See [`references/setup.md`](references/setup.md) for:
- Manual dependency installation
- Google rate limiting workarounds
- Metadata reset instructions

---

## 📄 License

MIT License — free to use, modify, and distribute.

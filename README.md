# 🖼️ Image Extractor — Claude Code Custom Skill

A custom skill for **Claude Code** that finds and downloads images for any topic, then saves them into a topic-named folder on your device.

This version is designed to be **Termux-friendly** and **Python 3.14 compatible**.

---

## ✨ Features

| Feature | Details |
|--------|---------|
| 🔎 Multi-source image discovery | Tries multiple public web sources instead of depending on one image search engine |
| 📁 Auto Folder Creation | Creates `/storage/emulated/0/DCIM/manga/{topic}/` automatically when available |
| 📐 Aspect Ratio Filter | Choose `9:16` (portrait) or `16:9` (landscape) |
| 🚫 Duplicate Detection | MD5 hash comparison prevents saving the same image twice |
| 🔁 Re-run Safe | Re-running skips already-downloaded images |
| 📱 Termux-friendly | Designed to run on Android Termux without `icrawler`, `lxml`, or `duckduckgo-search` |

---

## 📂 Repository Structure

```
image-extractor-skill/
├── SKILL.md                    ← Claude Code skill definition
├── README.md                   ← This file
├── scripts/
│   └── download_images.py      ← Core downloader
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

By default on Android/Termux:

```
/storage/emulated/0/DCIM/manga/
└── northern lights/
    ├── 001.jpg
    ├── 002.jpg
    ├── 003.jpg
    ├── 004.jpg
    ├── 005.jpg
    └── metadata.json
```

If external storage is not available, it falls back to the home directory.

---

## ⚙️ Manual Script Usage

You can also run the script directly without Claude Code:

```bash
python3 scripts/download_images.py --topic "northern lights" --ratio "16:9"
python3 scripts/download_images.py --topic "city skyline" --ratio "9:16"
python3 scripts/download_images.py --topic "Trump speaking at conference" --ratio "16:9" --count 20
```

---

## 📦 Dependencies

Install manually:

```bash
pip install requests Pillow
```

---

## 📋 Requirements

- Python 3.14+
- Claude Code with custom skills enabled
- Internet connection
- Termux storage permission if saving to `/storage/emulated/0/DCIM/manga/`

---

## 🛠️ Troubleshooting

- Run `termux-setup-storage` and allow storage access.
- If the folder falls back to your home directory, Android storage access is not active.
- If too few images are found, try a broader topic or a different ratio.

---

## 📄 License

MIT License — free to use, modify, and distribute.

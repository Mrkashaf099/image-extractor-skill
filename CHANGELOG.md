# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-17

### Added
- Initial release of Image Extractor Skill
- Google Images web scraper with cheerio and axios
- Support for 16:9 and 9:16 aspect ratio filtering
- Customizable minimum image size requirements
- SHA-256 based duplicate detection system
- Automatic folder creation in `~/ImageExtractor/`
- Topic-based organization with sanitized folder names
- Image metadata extraction using sharp
- Interactive CLI with prompt-sync
- Comprehensive error handling and logging
- Results summary with download/skip/fail counts
- File naming convention with resolution and aspect ratio
- Support for 5 images per topic download limit
- Tolerance-based aspect ratio validation (10% default)

### Features
- ✨ Smart image extraction from Google Images
- 📁 Organized local filesystem management
- 🔍 Quality control with aspect ratio and size validation
- 🔄 Intelligent duplicate detection
- 💾 Persistent hash tracking for deduplication
- 🎯 User-friendly interactive CLI
- 📊 Detailed extraction results and statistics

### Technical Details
- Built with Node.js and ES6 modules
- Zero dependency on browser automation (no Puppeteer/Playwright)
- Lightweight (~10-20MB runtime for 5 images)
- Cross-platform (Windows, macOS, Linux)

### Documentation
- Complete README with setup instructions
- Troubleshooting guide
- Project structure documentation
- Module responsibility breakdown
- Configuration guide

## [0.1.0] - Planning Phase
- Project specification and planning
- Architecture design
- Module structure planning

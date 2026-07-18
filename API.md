# API Documentation

Complete reference for all modules and methods in the Image Extractor Skill.

## Table of Contents
- [ImageExtractor](#imageextractor)
- [ImageScraper](#imagescraper)
- [FileManager](#filemanager)
- [AspectRatioValidator](#aspectratiovalidator)

---

## ImageExtractor

Main orchestration class that coordinates the entire image extraction workflow.

### Constructor

```javascript
const extractor = new ImageExtractor(fileManager);
```

**Parameters:**
- `fileManager` (FileManager): Instance of FileManager for file operations

### Methods

#### extractImages(topic, aspectRatios, minSize, maxImages)

Orchestrates the full image extraction pipeline: scraping, validation, and downloading.

```javascript
const results = await extractor.extractImages(
  'mountain landscape',
  ['16:9', '9:16'],
  '1920x1080',
  5
);
```

**Parameters:**
- `topic` (string): Search query for Google Images
- `aspectRatios` (array): Array of aspect ratio labels: `['16:9']`, `['9:16']`, or both
- `minSize` (string): Minimum size as "WIDTHxHEIGHT" (e.g., "1920x1080") or empty string
- `maxImages` (number): Maximum images to download (default: 5)

**Returns:** (Promise<Object>)
```javascript
{
  downloaded: ['image_1_1920x1080_16-9_123.jpg', ...],
  duplicates: ['image_2_1920x1080_16-9_124.jpg', ...],
  failed: ['https://example.com/image.jpg', ...]
}
```

**Throws:** Error if extraction fails

---

#### downloadImage(url)

Downloads a single image from a URL and returns the buffer.

```javascript
const imageBuffer = await extractor.downloadImage(
  'https://example.com/image.jpg'
);
```

**Parameters:**
- `url` (string): Full URL to image

**Returns:** (Promise<Buffer>) Image data as buffer

**Options applied:**
- Timeout: 10,000ms
- User-Agent: Chrome on Windows

**Throws:** Error if download fails

---

#### generateFilename(index, width, height)

Creates a descriptive filename for an image.

```javascript
const filename = extractor.generateFilename(1, 1920, 1080);
// Returns: "image_1_1920x1080_16-9_1234567890.jpg"
```

**Parameters:**
- `index` (number): Image sequence number
- `width` (number): Image width in pixels
- `height` (number): Image height in pixels

**Returns:** (string) Filename with pattern: `image_{index}_{width}x{height}_{ratio}_{timestamp}.jpg`

**Naming pattern explained:**
- `image_` - Prefix
- `1` - Sequential number
- `1920x1080` - Dimensions
- `16-9` - Aspect ratio classification
- `1234567890` - Unix timestamp for uniqueness

---

## ImageScraper

Handles web scraping of Google Images and image URL extraction.

### Constructor

```javascript
const scraper = new ImageScraper();
```

### Methods

#### scrapeGoogleImages(query, maxResults)

Searches Google Images and extracts image URLs.

```javascript
const urls = await scraper.scrapeGoogleImages(
  'sunset ocean waves',
  15
);
```

**Parameters:**
- `query` (string): Search term
- `maxResults` (number): Maximum URLs to return (default: 15)

**Returns:** (Promise<Array<string>>) Array of image URLs

**Implementation:**
- Sends GET request to Google Images with query parameters
- Parses HTML using Cheerio
- Filters URLs using `isValidImageUrl()`
- Removes duplicates
- Returns up to maxResults URLs

**Error handling:** Returns empty array if scraping fails

---

#### extractImageUrls(html, maxResults)

Parses HTML and extracts image URLs using multiple strategies.

```javascript
const urls = await scraper.extractImageUrls(htmlContent, 10);
```

**Parameters:**
- `html` (string): Raw HTML content from Google Images
- `maxResults` (number): Maximum URLs to extract

**Returns:** (Array<string>) Filtered and deduplicated URLs

**Parsing strategies:**
1. Extracts from JavaScript script tags
2. Searches for URL patterns: `https://...`
3. Validates each URL
4. Removes duplicates
5. Limits to maxResults

---

#### isValidImageUrl(url)

Validates if a URL is likely a legitimate image source.

```javascript
const isValid = scraper.isValidImageUrl(url);
```

**Parameters:**
- `url` (string): URL to validate

**Returns:** (boolean) True if URL appears to be a valid image

**Validation rules:**

**Excludes patterns:**
- google.com tracking URLs
- authentication URLs (accounts.google.com)
- CSS/font URLs
- JavaScript code
- Data URIs

**Includes patterns:**
- Image file extensions: `.jpg`, `.png`, `.gif`, `.webp`, `.bmp`
- Known image hosts: Unsplash, Pexels, Pixabay, Flickr, Imgur
- Google CDN URLs (gstatic.com, googleusercontent.com)

**Minimum length:** 20 characters (to avoid fragments)

---

#### scrapeGoogleImagesAlternative(query, maxResults)

Alternative scraping method using different parsing strategy.

```javascript
const urls = await scraper.scrapeGoogleImagesAlternative(
  'nature photography',
  10
);
```

**Parameters:**
- `query` (string): Search term
- `maxResults` (number): Maximum URLs to return

**Returns:** (Promise<Array<string>>) Array of image URLs

**Strategy:** Parses HTML `<img>` tags and looks for `src` and `data-src` attributes

**Use case:** Fallback when main scraper fails

---

## FileManager

Manages local filesystem operations, folder structure, and duplicate detection.

### Constructor

```javascript
const fileManager = new FileManager();
// Base directory: ~/ImageExtractor/
```

### Methods

#### initializeBaseDir()

Creates and initializes the base directory structure.

```javascript
await fileManager.initializeBaseDir();
// Creates ~/ImageExtractor/ and ~/ImageExtractor/.metadata/
```

**Returns:** (Promise<string>) Path to base directory

**Creates:**
- Main directory: `~/ImageExtractor/`
- Metadata subdirectory: `~/ImageExtractor/.metadata/`

**Error handling:** Throws error if creation fails

---

#### createTopicFolder(topic)

Creates a topic-specific folder with sanitized name.

```javascript
const path = await fileManager.createTopicFolder('Mountain Landscape!');
// Returns: ~/ImageExtractor/mountain-landscape/
```

**Parameters:**
- `topic` (string): Topic/search term

**Returns:** (Promise<string>) Full path to topic folder

**Sanitization rules:**
- Convert to lowercase
- Remove special characters (keep only alphanumeric and hyphens)
- Replace spaces with hyphens
- Remove consecutive hyphens
- Limit to 50 characters

**Examples:**
- "Mountain Landscape!" → "mountain-landscape"
- "Nature   Photography" → "nature-photography"
- "Sunset @ Beach $$$" → "sunset-beach"

---

#### sanitizeTopicName(topic)

Sanitizes topic name for safe folder creation.

```javascript
const sanitized = fileManager.sanitizeTopicName('Wild Cats & Dogs!');
// Returns: "wild-cats-dogs"
```

**Parameters:**
- `topic` (string): Raw topic string

**Returns:** (string) Safe folder name

---

#### calculateImageHash(filePath)

Calculates SHA-256 hash of image file for deduplication.

```javascript
const hash = await fileManager.calculateImageHash(
  '/home/user/ImageExtractor/mountain-landscape/image_1.jpg'
);
// Returns: "abc123def456..."
```

**Parameters:**
- `filePath` (string): Full path to image file

**Returns:** (Promise<string>) SHA-256 hash in hex format

**Hash algorithm:** SHA-256 (cryptographically secure)

**Use case:** Detect identical images across downloads and topics

---

#### isDuplicate(filePath)

Checks if image is duplicate based on hash comparison.

```javascript
const isDup = await fileManager.isDuplicate(filePath);
// Returns: true if hash already exists in hashMap
```

**Parameters:**
- `filePath` (string): Path to image file

**Returns:** (Promise<boolean>) True if duplicate found

**Logic:**
1. Calculate SHA-256 hash of file
2. Check if hash exists in hashMap
3. If new, add to map for future checks
4. Return duplicate status

---

#### saveImage(imageBuffer, topicFolder, filename)

Saves image buffer to topic folder and checks for duplicates.

```javascript
const result = await fileManager.saveImage(
  imageBuffer,
  '/home/user/ImageExtractor/mountain-landscape',
  'image_1_1920x1080_16-9_123.jpg'
);
```

**Parameters:**
- `imageBuffer` (Buffer): Image data from download
- `topicFolder` (string): Path to topic directory
- `filename` (string): Filename to save as

**Returns:** (Promise<Object>)
```javascript
{
  success: boolean,      // Whether save succeeded
  isDuplicate: boolean,  // Whether image was duplicate
  filePath: string|null  // Path if successful, null otherwise
}
```

**Process:**
1. Write buffer to file
2. Calculate hash of saved file
3. Check if duplicate exists
4. If duplicate, delete file and return isDuplicate: true
5. If unique, keep file and return success: true

---

#### loadExistingHashes(topicFolder)

Pre-loads hashes of existing images in a topic folder.

```javascript
await fileManager.loadExistingHashes(
  '/home/user/ImageExtractor/mountain-landscape'
);
```

**Parameters:**
- `topicFolder` (string): Path to topic directory

**Returns:** (Promise<void>)

**Behavior:**
- Finds all image files (.jpg, .jpeg, .png, .gif, .webp)
- Calculates hash for each
- Adds to hashMap for deduplication checks
- Called at start of extraction to detect existing images

---

#### getBaseDir()

Returns the base directory path.

```javascript
const baseDir = fileManager.getBaseDir();
// Returns: "/home/user/ImageExtractor"
```

**Returns:** (string) Base directory path

---

## AspectRatioValidator

Validates image dimensions against requested aspect ratios.

### Constructor

```javascript
const validator = new AspectRatioValidator(tolerance = 0.1);
// tolerance: 10% by default (0.1 = 10%)
```

**Parameters:**
- `tolerance` (number): Acceptable deviation from target ratio (0.0 to 1.0)

**Predefined ratios:**
- `16:9` = 1.777...
- `9:16` = 0.5625

---

### Methods

#### validateAspectRatio(width, height, requestedRatios)

Checks if image dimensions match any requested aspect ratio.

```javascript
const isValid = validator.validateAspectRatio(
  1920,
  1080,
  ['16:9', '9:16']
);
// Returns: true (1920x1080 is 16:9)
```

**Parameters:**
- `width` (number): Image width in pixels
- `height` (number): Image height in pixels
- `requestedRatios` (array): Aspect ratio labels to check against

**Returns:** (boolean) True if matches any requested ratio

**Tolerance logic:**
- Calculates image ratio: width/height
- Compares against each requested ratio
- Allows deviation up to tolerance percentage
- Returns true if any ratio matches

**Example with 10% tolerance:**
- Requested: 16:9 (1.777)
- Image ratio: 1.78 (1920x1080)
- Difference: (|1.78 - 1.777| / 1.777) = 0.0017 = 0.17%
- Result: ✅ PASS (0.17% < 10% tolerance)

---

#### getAspectRatioLabel(width, height)

Classifies image into aspect ratio category.

```javascript
const label = validator.getAspectRatioLabel(1920, 1080);
// Returns: "16-9"
```

**Parameters:**
- `width` (number): Image width
- `height` (number): Image height

**Returns:** (string) Ratio label:
- `"16-9"` - Landscape/wide
- `"9-16"` - Portrait/tall
- `"square"` - Equal dimensions
- `"landscape"` - Other wide ratio
- `"portrait"` - Other tall ratio
- `"unknown"` - Invalid input

**Classification logic:**
- Uses 10% tolerance for standard ratios
- Falls back to general landscape/portrait/square
- Returns "unknown" if dimensions invalid

---

#### getExactRatio(width, height)

Calculates exact aspect ratio as simplified fraction.

```javascript
const ratio = validator.getExactRatio(1920, 1080);
// Returns: "16:9"
```

**Parameters:**
- `width` (number): Image width
- `height` (number): Image height

**Returns:** (string) Ratio in "W:H" format

**Algorithm:**
1. Calculate GCD (Greatest Common Divisor)
2. Divide both by GCD
3. Return as "width:height" string

**Examples:**
- 1920x1080 → "16:9"
- 2560x1440 → "16:9"
- 1080x1920 → "9:16"
- 400x300 → "4:3"

---

#### validateMinimumSize(width, height, minWidth, minHeight)

Checks if image meets minimum size requirements.

```javascript
const isValid = validator.validateMinimumSize(
  1920,
  1080,
  800,
  600
);
// Returns: true
```

**Parameters:**
- `width` (number): Image width
- `height` (number): Image height
- `minWidth` (number): Minimum required width
- `minHeight` (number): Minimum required height

**Returns:** (boolean) True if both dimensions meet minimum

**Logic:** Both width AND height must be >= minimum values

---

## Type Definitions

### ImageResult
```typescript
{
  downloaded: string[],  // Saved filenames
  duplicates: string[],  // Skipped duplicate filenames
  failed: string[]       // Failed URLs
}
```

### SaveResult
```typescript
{
  success: boolean,      // Save succeeded
  isDuplicate: boolean,  // Was duplicate
  filePath: string|null  // Full path if successful
}
```

---

## Error Handling

### Common Errors

**NoImagesFoundError**
```javascript
console.error('⚠️  No images found');
// Causes: Invalid search term, network issue, rate limit
```

**DownloadTimeoutError**
```javascript
console.error('❌ Download failed: timeout');
// Cause: Image server slow, 10s timeout exceeded
```

**InvalidAspectRatioError**
```javascript
console.error('⏭️  Skipped: Wrong aspect ratio');
// Cause: Image doesn't match requested ratios
```

**DuplicateDetectedError**
```javascript
console.error('🔄 Duplicate detected, skipped');
// Cause: SHA-256 hash matches existing image
```

---

## Performance Notes

| Operation | Time | Notes |
|-----------|------|-------|
| Scrape 15 URLs | ~2-3s | Depends on network |
| Download 1 image | ~1-2s | Depends on server |
| Calculate hash | ~100ms | Per image |
| Validate ratio | <1ms | Per image |
| Total for 5 images | ~10-15s | Full pipeline |

---

## Usage Examples

### Basic Usage
```javascript
import ImageExtractor from './src/ImageExtractor.js';
import FileManager from './src/FileManager.js';

const fileManager = new FileManager();
await fileManager.initializeBaseDir();

const extractor = new ImageExtractor(fileManager);
const results = await extractor.extractImages(
  'mountain landscape',
  ['16:9'],
  '1920x1080',
  5
);

console.log(`Downloaded: ${results.downloaded.length}`);
```

### Advanced: Custom Validation
```javascript
const validator = new AspectRatioValidator(0.15); // 15% tolerance
const isValid = validator.validateAspectRatio(1000, 600, ['16:9']);
```

### Advanced: Batch Processing
```javascript
const topics = ['mountains', 'ocean', 'forest'];
for (const topic of topics) {
  const results = await extractor.extractImages(
    topic,
    ['16:9', '9:16'],
    '1920x1080',
    5
  );
  console.log(`${topic}: ${results.downloaded.length} images`);
}
```

---

For more information, see [README.md](./README.md) and [QUICKSTART.md](./QUICKSTART.md).

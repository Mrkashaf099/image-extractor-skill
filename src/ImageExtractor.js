import axios from 'axios';
import sharp from 'sharp';
import path from 'path';
import ImageScraper from './ImageScraper.js';
import AspectRatioValidator from './AspectRatioValidator.js';

class ImageExtractor {
  constructor(fileManager) {
    this.fileManager = fileManager;
    this.scraper = new ImageScraper();
    this.validator = new AspectRatioValidator();
  }

  /**
   * Main extraction method
   */
  async extractImages(topic, aspectRatios, minSize, maxImages = 5) {
    const results = {
      downloaded: [],
      duplicates: [],
      failed: []
    };

    try {
      // Get topic folder
      const topicFolder = await this.fileManager.createTopicFolder(topic);
      
      // Load existing image hashes for deduplication
      await this.fileManager.loadExistingHashes(topicFolder);

      // Scrape image URLs
      console.log(`🔎 Scraping Google Images for "${topic}"...`);
      const imageUrls = await this.scraper.scrapeGoogleImages(topic, maxImages * 3); // Get extra URLs for filtering

      if (imageUrls.length === 0) {
        console.log('⚠️  No images found');
        return results;
      }

      console.log(`📸 Found ${imageUrls.length} potential images, validating...\n`);

      let downloadedCount = 0;
      for (const url of imageUrls) {
        if (downloadedCount >= maxImages) break;

        try {
          // Download image
          console.log(`⬇️  Downloading: ${url.substring(0, 60)}...`);
          const imageBuffer = await this.downloadImage(url);

          if (!imageBuffer) {
            results.failed.push(url);
            continue;
          }

          // Validate aspect ratio
          const metadata = await sharp(imageBuffer).metadata();
          const { width, height } = metadata;

          // Check minimum size if specified
          if (minSize) {
            const [minWidth, minHeight] = minSize.split('x').map(Number);
            if (width < minWidth || height < minHeight) {
              console.log(`  ⏭️  Skipped: Too small (${width}x${height})`);
              results.failed.push(url);
              continue;
            }
          }

          // Validate aspect ratio
          const isValidAspectRatio = this.validator.validateAspectRatio(
            width,
            height,
            aspectRatios
          );

          if (!isValidAspectRatio) {
            console.log(`  ⏭️  Skipped: Wrong aspect ratio (${width}x${height})`);
            results.failed.push(url);
            continue;
          }

          // Save image
          const filename = this.generateFilename(downloadedCount + 1, width, height);
          const saveResult = await this.fileManager.saveImage(
            imageBuffer,
            topicFolder,
            filename
          );

          if (saveResult.isDuplicate) {
            console.log(`  🔄 Duplicate detected, skipped`);
            results.duplicates.push(filename);
          } else if (saveResult.success) {
            console.log(`  ✅ Saved: ${filename} (${width}x${height})`);
            results.downloaded.push(filename);
            downloadedCount++;
          } else {
            results.failed.push(url);
          }
        } catch (error) {
          console.error(`  ❌ Error processing image: ${error.message}`);
          results.failed.push(url);
        }
      }

      return results;
    } catch (error) {
      throw new Error(`Image extraction failed: ${error.message}`);
    }
  }

  /**
   * Download image from URL
   */
  async downloadImage(url) {
    try {
      const response = await axios.get(url, {
        responseType: 'arraybuffer',
        timeout: 10000,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
      });

      return Buffer.from(response.data, 'binary');
    } catch (error) {
      throw new Error(`Download failed: ${error.message}`);
    }
  }

  /**
   * Generate filename for image
   */
  generateFilename(index, width, height) {
    const timestamp = Date.now();
    const aspectRatio = this.validator.getAspectRatioLabel(width, height);
    return `image_${index}_${width}x${height}_${aspectRatio}_${timestamp}.jpg`;
  }
}

export default ImageExtractor;

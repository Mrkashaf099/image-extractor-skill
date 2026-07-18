import axios from 'axios';
import * as cheerio from 'cheerio';

class ImageScraper {
  constructor() {
    this.baseUrl = 'https://www.google.com/search';
    this.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36';
  }

  /**
   * Scrape Google Images for a given search term
   */
  async scrapeGoogleImages(query, maxResults = 15) {
    try {
      const params = {
        q: query,
        tbm: 'isch', // Image search
        ijn: 0
      };

      const response = await axios.get(this.baseUrl, {
        params,
        headers: {
          'User-Agent': this.userAgent,
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.5',
          'Referer': 'https://www.google.com/'
        },
        timeout: 15000
      });

      return this.extractImageUrls(response.data, maxResults);
    } catch (error) {
      console.error(`Scraping error: ${error.message}`);
      return [];
    }
  }

  /**
   * Extract image URLs from HTML response
   */
  extractImageUrls(html, maxResults) {
    const urls = [];
    
    try {
      // Parse the HTML
      const $ = cheerio.load(html);

      // Try multiple selectors as Google changes their structure
      const scripts = $('script');

      scripts.each((i, script) => {
        const content = $(script).html() || '';
        
        // Look for image URLs in the JavaScript data
        const urlMatches = content.match(/https?:\/\/[^\s"'<>]+/g);
        
        if (urlMatches) {
          urlMatches.forEach(url => {
            if (this.isValidImageUrl(url)) {
              urls.push(url);
            }
          });
        }
      });

      // Remove duplicates and limit results
      const uniqueUrls = [...new Set(urls)].slice(0, maxResults);
      return uniqueUrls;
    } catch (error) {
      console.error(`Error extracting URLs: ${error.message}`);
      return urls.slice(0, maxResults);
    }
  }

  /**
   * Validate if URL is likely an image
   */
  isValidImageUrl(url) {
    // Filter out Google tracking and unnecessary URLs
    const excludePatterns = [
      'google.com/images',
      'google.com/url',
      'maps.googleapis.com',
      'encrypted-tbn',
      't0.gstatic.com',
      'fonts.googleapis.com',
      'cse.google.com',
      'accounts.google.com',
      'javascript:',
      'data:image'
    ];

    // Check if URL contains common image extensions or is from image hosting
    const imagePatterns = [
      /\.(jpg|jpeg|png|gif|webp|bmp)$/i,
      /imgpx/,
      /gstatic\.com/,
      /googleusercontent\.com/,
      /unsplash\.com/,
      /pexels\.com/,
      /pixabay\.com/,
      /flickr\.com/,
      /imgur\.com/,
      /deviantart\.com/,
      /500px\.com/,
      /shutterstock\.com/
    ];

    const isExcluded = excludePatterns.some(pattern => url.includes(pattern));
    const isImage = imagePatterns.some(pattern => pattern.test(url));

    return !isExcluded && isImage && url.length > 20;
  }

  /**
   * Alternative method using custom Google Images API approach
   */
  async scrapeGoogleImagesAlternative(query, maxResults = 15) {
    try {
      // This uses a more reliable approach by parsing embedded JSON
      const params = {
        q: query,
        tbm: 'isch',
        ijn: 0
      };

      const response = await axios.get(this.baseUrl, {
        params,
        headers: {
          'User-Agent': this.userAgent
        },
        timeout: 15000
      });

      const urls = [];
      const $ = cheerio.load(response.data);

      // Look for image tags
      $('img').each((i, img) => {
        const src = $(img).attr('src');
        const dataSrc = $(img).attr('data-src');
        
        if (src && this.isValidImageUrl(src)) {
          urls.push(src);
        }
        if (dataSrc && this.isValidImageUrl(dataSrc)) {
          urls.push(dataSrc);
        }
      });

      return [...new Set(urls)].slice(0, maxResults);
    } catch (error) {
      console.error(`Alternative scraping error: ${error.message}`);
      return [];
    }
  }
}

export default ImageScraper;

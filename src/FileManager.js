import fs from 'fs-extra';
import path from 'path';
import crypto from 'crypto';
import os from 'os';

class FileManager {
  constructor() {
    this.baseDir = path.join(os.homedir(), 'ImageExtractor');
    this.hashMap = new Map(); // Store hashes for deduplication
  }

  /**
   * Initialize base directory structure
   */
  async initializeBaseDir() {
    try {
      await fs.ensureDir(this.baseDir);
      const metaDir = path.join(this.baseDir, '.metadata');
      await fs.ensureDir(metaDir);
      console.log(`✅ Base directory initialized: ${this.baseDir}`);
      return this.baseDir;
    } catch (error) {
      throw new Error(`Failed to initialize base directory: ${error.message}`);
    }
  }

  /**
   * Create a folder for the specific topic
   */
  async createTopicFolder(topic) {
    try {
      const sanitizedTopic = this.sanitizeTopicName(topic);
      const topicDir = path.join(this.baseDir, sanitizedTopic);
      await fs.ensureDir(topicDir);
      return topicDir;
    } catch (error) {
      throw new Error(`Failed to create topic folder: ${error.message}`);
    }
  }

  /**
   * Sanitize topic name for folder creation
   */
  sanitizeTopicName(topic) {
    return topic
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .slice(0, 50);
  }

  /**
   * Calculate hash of image file for deduplication
   */
  async calculateImageHash(filePath) {
    try {
      const content = await fs.readFile(filePath);
      return crypto.createHash('sha256').update(content).digest('hex');
    } catch (error) {
      console.error(`Error calculating hash for ${filePath}:`, error.message);
      return null;
    }
  }

  /**
   * Check if image is duplicate based on hash
   */
  async isDuplicate(filePath) {
    const hash = await this.calculateImageHash(filePath);
    if (!hash) return false;

    if (this.hashMap.has(hash)) {
      return true;
    }
    this.hashMap.set(hash, filePath);
    return false;
  }

  /**
   * Save image file to topic folder
   */
  async saveImage(imageBuffer, topicFolder, filename) {
    try {
      const filePath = path.join(topicFolder, filename);
      await fs.writeFile(filePath, imageBuffer);
      
      // Check for duplicates
      const isDup = await this.isDuplicate(filePath);
      if (isDup) {
        await fs.remove(filePath);
        return { success: false, isDuplicate: true, filePath: null };
      }

      return { success: true, isDuplicate: false, filePath };
    } catch (error) {
      console.error(`Error saving image: ${error.message}`);
      return { success: false, isDuplicate: false, filePath: null };
    }
  }

  /**
   * Get all existing image hashes in topic folder for initial dedup check
   */
  async loadExistingHashes(topicFolder) {
    try {
      if (!await fs.pathExists(topicFolder)) {
        return;
      }

      const files = await fs.readdir(topicFolder);
      for (const file of files) {
        if (['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(path.extname(file).toLowerCase())) {
          const filePath = path.join(topicFolder, file);
          const hash = await this.calculateImageHash(filePath);
          if (hash) {
            this.hashMap.set(hash, filePath);
          }
        }
      }
    } catch (error) {
      console.error(`Error loading existing hashes: ${error.message}`);
    }
  }

  /**
   * Get base directory
   */
  getBaseDir() {
    return this.baseDir;
  }
}

export default FileManager;

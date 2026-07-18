#!/usr/bin/env node

import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';
import prompt from 'prompt-sync';
import ImageExtractor from './src/ImageExtractor.js';
import FileManager from './src/FileManager.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const input = prompt({ sigint: true });

async function main() {
  console.log('\n╔════════════════════════════════════════╗');
  console.log('║   Google Image Extractor - Claude Skill   ║');
  console.log('╚════════════════════════════════════════╝\n');

  try {
    // Initialize file manager
    const fileManager = new FileManager();
    await fileManager.initializeBaseDir();

    // Get user inputs
    const topic = input('Enter search topic (e.g., "mountain landscape"): ');
    if (!topic.trim()) {
      console.error('❌ Topic cannot be empty');
      process.exit(1);
    }

    console.log('\nAspect Ratio Options:');
    console.log('  1) 16:9 (Landscape/Wide)');
    console.log('  2) 9:16 (Portrait/Tall)');
    console.log('  3) Both');

    const aspectRatioChoice = input('Select aspect ratio (1-3): ').trim();
    let aspectRatios = [];

    switch (aspectRatioChoice) {
      case '1':
        aspectRatios = ['16:9'];
        break;
      case '2':
        aspectRatios = ['9:16'];
        break;
      case '3':
        aspectRatios = ['16:9', '9:16'];
        break;
      default:
        console.warn('⚠️  Invalid choice, defaulting to both aspect ratios');
        aspectRatios = ['16:9', '9:16'];
    }

    const minSize = input('Enter minimum image size (e.g., "800x600" or press Enter for no minimum): ').trim();

    console.log('\n🔍 Starting image extraction...\n');

    // Create topic folder
    const topicFolder = await fileManager.createTopicFolder(topic);
    console.log(`📁 Topic folder created: ${topicFolder}`);

    // Initialize extractor
    const extractor = new ImageExtractor(fileManager);

    // Extract images
    const results = await extractor.extractImages(topic, aspectRatios, minSize, 5);

    if (results.downloaded.length === 0) {
      console.log('❌ No images were downloaded. Please try a different search term.');
      process.exit(0);
    }

    // Display results
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║              RESULTS                   ║');
    console.log('╚════════════════════════════════════════╝\n');
    console.log(`✅ Downloaded: ${results.downloaded.length} images`);
    console.log(`⏭️  Skipped (duplicates): ${results.duplicates.length}`);
    console.log(`❌ Failed: ${results.failed.length}`);
    console.log(`📁 Saved to: ${topicFolder}\n`);

    if (results.downloaded.length > 0) {
      console.log('Downloaded images:');
      results.downloaded.forEach((file, i) => {
        console.log(`  ${i + 1}. ${file}`);
      });
    }

    if (results.duplicates.length > 0) {
      console.log('\nSkipped duplicates:');
      results.duplicates.forEach((file, i) => {
        console.log(`  ${i + 1}. ${file}`);
      });
    }

    if (results.failed.length > 0) {
      console.log('\nFailed downloads:');
      results.failed.forEach((file, i) => {
        console.log(`  ${i + 1}. ${file}`);
      });
    }

    console.log('\n✨ Image extraction complete!');
  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

main().catch(console.error);

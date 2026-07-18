class AspectRatioValidator {
  constructor(tolerance = 0.1) {
    this.tolerance = tolerance; // 10% tolerance for aspect ratio matching
    this.aspectRatios = {
      '16:9': 16 / 9,
      '9:16': 9 / 16
    };
  }

  /**
   * Validate if image dimensions match requested aspect ratios
   */
  validateAspectRatio(width, height, requestedRatios) {
    if (!width || !height || requestedRatios.length === 0) {
      return true; // Allow if no specific ratio requested
    }

    const imageRatio = width / height;

    // Check if image matches any of the requested aspect ratios
    return requestedRatios.some(ratioLabel => {
      const targetRatio = this.aspectRatios[ratioLabel];
      if (!targetRatio) return false;

      // Calculate the difference
      const difference = Math.abs(imageRatio - targetRatio) / targetRatio;
      return difference <= this.tolerance;
    });
  }

  /**
   * Classify image aspect ratio
   */
  getAspectRatioLabel(width, height) {
    if (!width || !height) return 'unknown';

    const ratio = width / height;
    
    if (Math.abs(ratio - (16 / 9)) < 0.1) {
      return '16-9';
    } else if (Math.abs(ratio - (9 / 16)) < 0.1) {
      return '9-16';
    } else if (Math.abs(ratio - 1) < 0.1) {
      return 'square';
    } else if (ratio > 1) {
      return 'landscape';
    } else {
      return 'portrait';
    }
  }

  /**
   * Get exact aspect ratio as string
   */
  getExactRatio(width, height) {
    if (!width || !height) return '0:0';
    
    const gcd = (a, b) => b === 0 ? a : gcd(b, a % b);
    const divisor = gcd(width, height);
    
    return `${width / divisor}:${height / divisor}`;
  }

  /**
   * Validate minimum size
   */
  validateMinimumSize(width, height, minWidth, minHeight) {
    return width >= minWidth && height >= minHeight;
  }
}

export default AspectRatioValidator;

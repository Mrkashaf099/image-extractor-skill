# Contributing to Image Extractor Skill

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

### Fork and Clone
```bash
git clone https://github.com/yourusername/image-extractor-skill.git
cd image-extractor-skill
npm install
```

### Development Setup
```bash
# Install dependencies
npm install

# Run in watch mode (optional)
npm run dev

# Run normally
npm start
```

## Code Structure

```
src/
├── ImageExtractor.js       # Orchestration logic
├── ImageScraper.js         # Google Images scraper
├── FileManager.js          # File system operations
└── AspectRatioValidator.js # Image dimension validation

index.js                     # CLI entry point
```

## How to Contribute

### Bug Reports
1. Check existing issues first
2. Include:
   - Search term that failed
   - Expected vs actual behavior
   - System info (OS, Node version)
   - Full error message

### Feature Requests
1. Describe the feature clearly
2. Explain the use case
3. Provide examples if possible

### Code Contributions

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make changes**
   - Keep commits focused and atomic
   - Write clear commit messages
   - Follow the existing code style

3. **Test your changes**
   ```bash
   # Manual testing
   npm start
   # [follow prompts and verify behavior]
   ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Reference related issues
   - Describe what changed and why
   - Include testing notes

## Code Style Guidelines

### Naming Conventions
- **Classes:** PascalCase (e.g., `ImageExtractor`)
- **Methods/functions:** camelCase (e.g., `extractImages()`)
- **Constants:** UPPER_SNAKE_CASE (e.g., `MAX_RETRIES`)
- **Variables:** camelCase (e.g., `imageUrl`)

### File Structure
```javascript
// 1. Imports
import axios from 'axios';
import sharp from 'sharp';

// 2. Class definition
class MyClass {
  // Constructor
  constructor() { }
  
  // Public methods
  publicMethod() { }
  
  // Private methods (prefix with _)
  _privateMethod() { }
}

// 3. Export
export default MyClass;
```

### Comments
```javascript
/**
 * Brief description of what the method does
 * @param {Type} paramName - Description
 * @returns {Type} Description
 */
methodName(paramName) {
  // Inline comments for complex logic
  const result = complexCalculation();
  return result;
}
```

### Error Handling
```javascript
try {
  // Attempt operation
  const result = await riskyOperation();
  return result;
} catch (error) {
  console.error(`Operation failed: ${error.message}`);
  throw new Error(`Context: ${error.message}`);
}
```

## Testing Guidelines

### Manual Testing Checklist
- [ ] Script runs without errors
- [ ] Images are downloaded correctly
- [ ] Aspect ratio validation works
- [ ] Duplicate detection functions
- [ ] Files save to correct location
- [ ] Results summary is accurate

### Test Scenarios
1. **Valid search term** → 5 images downloaded
2. **Invalid search term** → Graceful error
3. **Duplicate images** → Properly detected and skipped
4. **Wrong aspect ratio** → Filtered correctly
5. **Too small images** → Rejected with reason
6. **No internet** → Error message shown

## Performance Considerations

### Optimization Tips
- Minimize API calls
- Cache downloaded images locally
- Batch operations where possible
- Use streaming for large files

### Performance Testing
```bash
# Time execution
time npm start
```

## Documentation

### Update These Files
- `README.md` - Main documentation
- `QUICKSTART.md` - Quick start guide
- `CHANGELOG.md` - Version history
- Inline code comments

### Documentation Style
- Clear and concise
- Include examples
- Use markdown formatting
- Keep technical level appropriate

## Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `style:` Code style (no logic change)
- `refactor:` Code refactoring
- `perf:` Performance improvement
- `test:` Tests
- `chore:` Maintenance

### Examples
```
feat(scraper): add support for Unsplash images

Add new ImageScraper method to support Unsplash API
alongside Google Images. Maintains aspect ratio and
size validation for both sources.

Fixes #123
```

```
fix(validator): correct aspect ratio tolerance calculation

The tolerance check was using > instead of >=, causing
edge case failures. Updated to use correct comparison.

Fixes #456
```

## Pull Request Process

1. **Title:** Clear, descriptive title
2. **Description:** What and why (not just how)
3. **Related Issues:** Reference with `Fixes #123`
4. **Testing:** Describe manual testing done
5. **Checklist:**
   - [ ] Code follows style guidelines
   - [ ] Documentation updated
   - [ ] Manual testing completed
   - [ ] No console errors/warnings
   - [ ] Commit messages are clear

### Example PR Description
```
## Description
This PR adds support for Unsplash image source, allowing 
users to search and download from multiple platforms.

## Changes
- Added UnspashScraper.js module
- Updated ImageExtractor to support multiple sources
- Added configuration for source selection

## Testing
- Tested with "mountain landscape" query
- Verified aspect ratio filtering works
- Confirmed deduplication across sources
- Manual testing with 20+ searches

## Related Issues
Fixes #123
Relates to #456

## Type of Change
- [x] New feature
- [ ] Bug fix
- [ ] Breaking change
- [ ] Documentation
```

## Review Process

### What Reviewers Look For
- ✅ Code quality and style
- ✅ Tests and validation
- ✅ Documentation completeness
- ✅ Performance impact
- ✅ Backward compatibility

### Addressing Feedback
- Respond respectfully to comments
- Make requested changes in new commits
- Push updates (don't force push to main PR branch)
- Request re-review when ready

## Common Pitfalls to Avoid

❌ **Don't:**
- Commit node_modules
- Leave console.log() statements
- Create overly large PRs (100+ lines)
- Ignore existing code style
- Break backward compatibility
- Forget to update documentation

✅ **Do:**
- Write descriptive commit messages
- Test thoroughly before submitting
- Keep PRs focused and reviewable
- Follow existing patterns
- Update relevant documentation
- Consider edge cases

## Questions?

- Check [README.md](./README.md) for general info
- Review [QUICKSTART.md](./QUICKSTART.md) for usage
- Check existing issues/PRs for similar questions
- Open a discussion issue to ask questions

## Code of Conduct

- Be respectful and inclusive
- Focus on the code, not the person
- Help others learn and grow
- Report problematic behavior

Thank you for contributing! 🚀

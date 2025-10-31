# 🤝 Contributing to SLT Chatbot

Thank you for considering contributing to the SLT Chatbot project! We welcome contributions from the community.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

## 📜 Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code:

- **Be respectful**: Treat everyone with respect
- **Be collaborative**: Work together towards common goals
- **Be inclusive**: Welcome newcomers and diverse perspectives
- **Be professional**: Keep discussions focused and constructive

## 🚀 Getting Started

### Prerequisites

Before contributing, ensure you have:
- Read the [README.md](README.md)
- Completed the [QUICKSTART.md](QUICKSTART.md) guide
- Set up your development environment
- Tested the application locally

### Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/KesharaGunathilaka/SLT_AI_Chatbot
cd SLT_AI_Chatbot

# Add upstream remote
git remote add upstream https://github.com/KesharaGunathilaka/SLT_AI_Chatbot

# Verify remotes
git remote -v
```

## 💻 Development Workflow

### 1. Create a Branch

Always create a new branch for your work:

```bash
# Update your fork
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

**Branch naming conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/improvements
- `chore/` - Maintenance tasks

### 2. Make Changes

- Write clear, concise commit messages
- Keep commits atomic (one logical change per commit)
- Test your changes thoroughly
- Update documentation as needed

### 3. Commit Changes

```bash
# Stage your changes
git add .

# Commit with a descriptive message
git commit -m "feat: add support for custom LLM models"
```

**Commit message format:**
```
<type>: <subject>

<body (optional)>

<footer (optional)>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Build process or auxiliary tool changes

**Examples:**
```bash
git commit -m "feat: add streaming response support"
git commit -m "fix: resolve memory leak in vectorization"
git commit -m "docs: update API documentation with examples"
git commit -m "refactor: simplify embedding generation logic"
```

### 4. Keep Your Branch Updated

```bash
# Fetch upstream changes
git fetch upstream

# Rebase your branch
git rebase upstream/main

# Resolve conflicts if any
# Then continue rebase
git add .
git rebase --continue
```

### 5. Push Changes

```bash
# Push to your fork
git push origin feature/your-feature-name

# If you rebased, force push (with lease for safety)
git push --force-with-lease origin feature/your-feature-name
```

## 📏 Coding Standards

### Python (Backend)

Follow [PEP 8](https://pep8.org/) style guide:

```python
# Good
def calculate_embeddings(text: str, model: str = "bge-m3") -> List[float]:
    """Generate embeddings for input text.
    
    Args:
        text: Input text to embed
        model: Name of embedding model
        
    Returns:
        List of embedding values
    """
    # Implementation
    pass

# Bad
def calcEmbed(txt,mdl="bge-m3"):
    #no docs
    pass
```

**Guidelines:**
- Use type hints
- Write docstrings for functions/classes
- Maximum line length: 88 characters (Black formatter)
- Use meaningful variable names
- Add comments for complex logic

**Formatting:**
```bash
# Install Black formatter
pip install black

# Format code
black backend/
```

### JavaScript/React (Frontend)

Follow modern JavaScript/React best practices:

```javascript
// Good - Named export with JSDoc
/**
 * Chat message component
 * @param {Object} props - Component props
 * @param {string} props.message - Message text
 * @param {string} props.sender - Message sender
 */
export const ChatMessage = ({ message, sender }) => {
  return (
    <div className={`message ${sender}`}>
      {message}
    </div>
  );
};

// Bad
export default function m(p) {
  return <div>{p.m}</div>;
}
```

**Guidelines:**
- Use functional components with hooks
- Destructure props
- Use meaningful component/variable names
- Keep components small and focused
- Use ES6+ features

**Linting:**
```bash
# Run ESLint
cd frontend
npm run lint

# Fix auto-fixable issues
npm run lint -- --fix
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

**Writing tests:**
```python
import pytest
from app import app

@pytest.mark.asyncio
async def test_chat_endpoint():
    """Test chat endpoint with valid input."""
    # Setup
    payload = {"message": "test question"}
    
    # Execute
    response = await client.post("/chat", json=payload)
    
    # Assert
    assert response.status_code == 200
    assert "reply" in response.json()
```

### Frontend Tests

```bash
cd frontend

# Install test dependencies
npm install --save-dev @testing-library/react vitest

# Run tests
npm run test
```

### Manual Testing

Before submitting:
1. ✅ Test all modified features
2. ✅ Test edge cases
3. ✅ Verify UI changes in multiple browsers
4. ✅ Check console for errors
5. ✅ Test with different LLM providers

## 📤 Submitting Changes

### Pull Request Process

1. **Update Documentation**
   - Update README.md if needed
   - Add/update API documentation
   - Update CHANGELOG.md (if exists)

2. **Create Pull Request**
   ```bash
   # Push your branch
   git push origin feature/your-feature-name
   
   # Go to GitHub and create PR
   ```

3. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation update
   - [ ] Performance improvement
   
   ## Testing
   - [ ] Tested locally
   - [ ] Added/updated tests
   - [ ] All tests passing
   
   ## Screenshots (if applicable)
   Add screenshots for UI changes
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] No new warnings
   ```

4. **Review Process**
   - Wait for maintainer review
   - Address feedback promptly
   - Keep PR focused (one feature/fix per PR)
   - Be responsive to comments

5. **After Merge**
   ```bash
   # Update your local repository
   git checkout main
   git pull upstream main
   
   # Delete feature branch
   git branch -d feature/your-feature-name
   git push origin --delete feature/your-feature-name
   ```

## 🐛 Reporting Bugs

### Before Reporting

1. Check if bug already reported
2. Verify bug exists in latest version
3. Gather relevant information

### Bug Report Template

```markdown
**Describe the bug**
Clear description of what the bug is

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen

**Screenshots**
Add screenshots if applicable

**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.10.0]
- Node.js: [e.g., 18.17.0]
- Browser: [e.g., Chrome 120]

**Additional context**
Any other relevant information
```

## 💡 Feature Requests

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
Clear description of the problem

**Describe the solution you'd like**
Clear description of desired solution

**Describe alternatives you've considered**
Alternative solutions or features

**Additional context**
Mockups, examples, or references
```

## 📞 Questions?

- 💬 Open a [GitHub Discussion](https://github.com/KesharaGunathilaka/SLT_AI_Chatbot/discussions)
- 🐛 Check existing [Issues](https://github.com/KesharaGunathilaka/SLT_AI_Chatbot/issues)
- 📧 Contact maintainers

## 🎓 First Time Contributors

New to open source? Here are some good first issues:
- Documentation improvements
- Adding tests
- Fixing typos
- Updating dependencies
- Adding comments to complex code

Look for issues labeled:
- `good first issue`
- `help wanted`
- `documentation`

## 🏆 Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes
- Git commit history

Thank you for contributing! 🎉

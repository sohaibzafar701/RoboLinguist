# Contributing to RoboLinguist

Thank you for your interest in contributing to RoboLinguist! We welcome contributions from the robotics and AI community to help advance natural language interfaces for robot fleet management.

## 🎯 **Project Vision**

RoboLinguist aims to democratize robot control by enabling natural language interaction with autonomous robot fleets. We're building a production-ready system that bridges the gap between human intuition and robotic precision.

## 🚀 **Getting Started**

### Prerequisites

- Python 3.8+
- Git
- Basic understanding of robotics concepts
- Familiarity with ROS2 (helpful but not required)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/RoboLinguist.git
   cd RoboLinguist
   ```

2. **Set Up Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python setup_config.py
   ```

3. **Run Tests**
   ```bash
   python -m pytest tests/
   python run_webots_demo.py  # Integration test
   ```

## 🛠️ **Development Workflow**

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch for new features
- `feature/feature-name` - Individual feature development
- `hotfix/issue-description` - Critical bug fixes

### Making Changes

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow our coding standards (see below)
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   # Run unit tests
   python -m pytest tests/

   # Run integration tests
   python run_webots_demo.py

   # Check code quality
   flake8 .
   black --check .
   ```

4. **Commit and Push**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**
   - Use our PR template
   - Include clear description of changes
   - Reference related issues
   - Ensure all checks pass

## 📋 **Contribution Guidelines**

### Code Standards

- **Python Style**: Follow PEP 8, use Black formatter
- **Documentation**: Docstrings for all public functions/classes
- **Type Hints**: Use type annotations for better code clarity
- **Error Handling**: Implement proper exception handling
- **Logging**: Use structured logging with appropriate levels

### Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(safety): add collision avoidance system
fix(translator): resolve formation command parsing issue
docs(readme): update installation instructions
```

### Testing Requirements

- **Unit Tests**: All new functions must have unit tests
- **Integration Tests**: Complex features need integration tests
- **Coverage**: Maintain >80% test coverage
- **Safety Tests**: Critical safety features require comprehensive testing

### Documentation Standards

- **README Updates**: Update README for new features
- **API Documentation**: Document all public APIs
- **Code Comments**: Explain complex logic and algorithms
- **Examples**: Provide usage examples for new features

## 🎯 **Areas for Contribution**

### High Priority

- **Path Planning Algorithms** (Task 8)
- **Web Interface Development** (Task 9)
- **Performance Optimization**
- **Additional LLM Model Support**
- **Real Robot Integration Testing**

### Medium Priority

- **Advanced Formation Patterns**
- **Voice Command Integration**
- **Multi-Language Support**
- **Enhanced Safety Rules**
- **Gazebo Integration**

### Documentation & Community

- **Tutorial Creation**
- **Video Demonstrations**
- **Blog Posts & Articles**
- **Community Support**
- **Translation to Other Languages**

## 🐛 **Bug Reports**

When reporting bugs, please include:

1. **Environment Information**
   - OS and version
   - Python version
   - RoboLinguist version
   - Hardware specifications

2. **Reproduction Steps**
   - Clear step-by-step instructions
   - Minimal code example
   - Expected vs actual behavior

3. **Logs and Screenshots**
   - Relevant log outputs
   - Error messages
   - Screenshots if applicable

4. **Additional Context**
   - Related issues or PRs
   - Potential solutions you've tried

## 💡 **Feature Requests**

For new features, please provide:

1. **Problem Statement**
   - What problem does this solve?
   - Who would benefit from this feature?

2. **Proposed Solution**
   - Detailed description of the feature
   - How it would work
   - Integration points with existing code

3. **Alternatives Considered**
   - Other approaches you've considered
   - Why this approach is preferred

4. **Implementation Notes**
   - Technical considerations
   - Potential challenges
   - Required resources

## 🏆 **Recognition**

Contributors will be recognized in:

- **README Contributors Section**
- **Release Notes**
- **Project Documentation**
- **Conference Presentations** (with permission)

## 📞 **Getting Help**

- **GitHub Discussions**: For general questions and ideas
- **GitHub Issues**: For bug reports and feature requests
- **Discord Community**: [Join our Discord](https://discord.gg/robolinguist)
- **Email**: contribute@robolinguist.dev

## 🔒 **Security**

For security vulnerabilities, please email security@robolinguist.dev instead of creating public issues.

## 📄 **License**

By contributing to RoboLinguist, you agree that your contributions will be licensed under the MIT License.

## 🙏 **Code of Conduct**

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of background, experience level, or identity.

### Expected Behavior

- Be respectful and constructive in all interactions
- Welcome newcomers and help them get started
- Focus on what's best for the community and project
- Show empathy towards other community members

### Unacceptable Behavior

- Harassment, discrimination, or offensive language
- Personal attacks or trolling
- Publishing private information without permission
- Any conduct that would be inappropriate in a professional setting

### Enforcement

Project maintainers are responsible for clarifying standards and will take appropriate action in response to unacceptable behavior.

---

## 🚀 **Ready to Contribute?**

1. Check our [Good First Issues](https://github.com/sohaibzafar701/RoboLinguist/labels/good%20first%20issue)
2. Join our [Discord Community](https://discord.gg/robolinguist)
3. Read through the codebase to understand the architecture
4. Start with documentation improvements or small bug fixes
5. Gradually work on more complex features

**Thank you for helping make robot control more accessible to everyone!** 🤖✨

---

*Last updated: January 2025*
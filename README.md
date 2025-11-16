# DevRules

A flexible CLI tool for enforcing development guidelines across your projects.

## Features

- ✅ Branch naming validation
- ✅ Commit message format checking
- ✅ Pull Request size and title validation
- ⚙️ Configurable via TOML files
- 🔌 Easy Git hooks integration

## Installation
```bash
pip install devrules
```

Or for development:
```bash
git clone https://github.com/pedroifgonzalez/devrules
cd devrules
pip install -e .
```

## Quick Start

1. Generate a configuration file:
```bash
devrules init-config
```

2. Customize `.devrules.toml` to your needs

3. Use in your workflow:
```bash
# Check branch name
devrules check-branch feature/123-login-page

# Check commit message
devrules check-commit .git/COMMIT_EDITMSG

# Check pull request
export GH_TOKEN=your_github_token
devrules check-pr owner repo 42
```

## Configuration

Create a `.devrules.toml` file in your project root:
```toml
[branch]
pattern = "^(feature|bugfix|hotfix|release|docs)/(\\d+-)?[a-z0-9-]+"
prefixes = ["feature", "bugfix", "hotfix", "release", "docs"]

[commit]
tags = ["WIP", "FTR", "FIX", "DOCS", "TST"]
pattern = "^\\[({tags})\\].+"
min_length = 10
max_length = 100

[pr]
max_loc = 400
max_files = 20
require_title_tag = true
```

## Git Hooks Integration

Add to `.git/hooks/commit-msg`:
```bash
#!/bin/bash
devrules check-commit "$1" || exit 1
```

Add to `.git/hooks/pre-push`:
```bash
#!/bin/bash
current_branch=$(git symbolic-ref --short HEAD)
devrules check-branch "$current_branch" || exit 1
```

## Commands

- `devrules check-branch <name>` - Validate branch name
- `devrules check-commit <file>` - Validate commit message
- `devrules check-pr <owner> <repo> <pr>` - Validate PR
- `devrules init-config` - Generate config file

## Development
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Lint
ruff check src/
```

## License

MIT

# DevRules

[![PyPI version](https://badge.fury.io/py/devrules.svg)](https://badge.fury.io/py/devrules)
[![Python Versions](https://img.shields.io/pypi/pyversions/devrules.svg)](https://pypi.org/project/devrules/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A flexible CLI tool for enforcing development guidelines across your projects.

## 🚀 Features

- ✅ **Branch naming validation** - Enforce consistent branch naming conventions
- ✅ **Commit message format checking** - Validate commit message structure
- ✅ **Pull Request validation** - Check PR size and title format
- ✅ **Deployment workflow** - Manage deployments across environments with Jenkins integration
- ⚙️ **Configurable via TOML** - Customize all rules to match your workflow
- 🔌 **Git hooks integration** - Automatic validation in your Git workflow
- 🎨 **Interactive branch creation** - User-friendly branch creation wizard
- 🌐 **GitHub API integration** - Validate PRs directly from GitHub
- 📊 **TUI Dashboard** - Interactive terminal dashboard for metrics and issue tracking

## 📦 Installation
```bash
pip install devrules
```

## 🎯 Quick Start

1. **Initialize configuration:**
```bash
devrules init-config
```

2. **Create a branch interactively:**
```bash
devrules create-branch
```

3. **Validate a branch name:**
```bash
devrules check-branch feature/123-new-feature
```

4. **Validate a commit message:**
```bash
devrules check-commit .git/COMMIT_EDITMSG
```

5. **Validate a Pull Request:**
```bash
export GH_TOKEN=your_github_token
devrules check-pr owner repo 42
```

6. **Deploy to an environment:**
```bash
# Configure deployment settings in .devrules.toml first
devrules deploy dev --branch feature/123-new-feature

# Or check deployment readiness without deploying
devrules check-deployment staging
```

7. **Launch the TUI Dashboard:**
```bash
# Install with TUI support first
pip install "devrules[tui]"

# Run the dashboard
devrules dashboard
```

## ⚙️ Configuration

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
gpg_sign = false  # Sign commits with GPG
protected_branch_prefixes = ["staging-"]  # Block direct commits to these branches

[pr]
max_loc = 400
max_files = 20
require_title_tag = true
```

## 🔗 Git Hooks Integration

### Automatic Installation

Install git hooks with a single command:

```bash
devrules install-hooks
```

This creates a `commit-msg` hook that:
1. Validates commit messages using devrules
2. Runs any existing pre-commit hooks (if `pre-commit` is installed)

To uninstall:
```bash
devrules uninstall-hooks
```

### Manual Setup

**Commit message validation:**
```bash
# .git/hooks/commit-msg
#!/bin/bash
devrules check-commit "$1" || exit 1
```

**Branch validation before push:**
```bash
# .git/hooks/pre-push
#!/bin/bash
current_branch=$(git symbolic-ref --short HEAD)
devrules check-branch "$current_branch" || exit 1
```

## ⌨️ Command Aliases

Most commands have short aliases for convenience:

| Command | Alias | Description |
|---------|-------|-------------|
| `check-branch` | `cb` | Validate branch name |
| `check-commit` | `cc` | Validate commit message |
| `check-pr` | `cpr` | Validate pull request |
| `create-branch` | `nb` | Create new branch |
| `commit` | `ci` | Commit with validation |
| `create-pr` | `pr` | Create pull request |
| `init-config` | `init` | Generate config file |
| `install-hooks` | `ih` | Install git hooks |
| `uninstall-hooks` | `uh` | Remove git hooks |
| `list-issues` | `li` | List GitHub issues |
| `describe-issue` | `di` | Show issue details |
| `update-issue-status` | `uis` | Update issue status |
| `list-owned-branches` | `lob` | List your branches |
| `delete-branch` | `db` | Delete a branch |
| `delete-merged` | `dm` | Delete merged branches |
| `dashboard` | `dash` | Open TUI dashboard |
| `deploy` | `dep` | Deploy to environment |
| `check-deployment` | `cd` | Check deployment status |
| `build-enterprise` | `be` | Build enterprise package |

## 📚 Documentation

For full documentation, visit [GitHub](https://github.com/pedroifgonzalez/devrules).

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with [Typer](https://typer.tiangolo.com/) for an amazing CLI experience.

## 📧 Contact

- GitHub: [@pedroifgonzalez](https://github.com/pedroifgonzalez)
- Email: pedroifgonzalez@gmail.com

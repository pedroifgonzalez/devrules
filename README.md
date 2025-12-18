<table>
  <tr>
    <td><img src="devrules.png" alt="DevRules Logo" width="150"></td>
    <td>
      <h1>DevRules</h1>
      <p>Automate your internal rules. Reduce errors. Accelerate onboarding.</p>
      <p>
        <a href="https://badge.fury.io/py/devrules"><img src="https://badge.fury.io/py/devrules.svg" alt="PyPI version"></a>
        <a href="https://pypi.org/project/devrules/"><img src="https://img.shields.io/pypi/pyversions/devrules.svg" alt="Python Versions"></a>
        <a href="LICENSE"><img src="https://img.shields.io/badge/License-BSL%201.1-blue.svg" alt="License: BSL 1.1"></a>
      </p>
    </td>
  </tr>
</table>

## 📜 License

DevRules is licensed under the **Business Source License 1.1 (BSL)**.

**What this means:**
- ✅ **Free for small companies** - Organizations with < 100 employees can use in production
- ✅ **Free for non-production** - Anyone can use for development, testing, and evaluation
- ✅ **Source available** - Full source code is visible and modifiable
- ✅ **Becomes open source** - Converts to Apache 2.0 license on 2029-12-06 (4 years)
- 💼 **Commercial license available** - For larger organizations or production use beyond the grant

**Need a commercial license?** Contact pedroifgonzalez@gmail.com

See [LICENSE](LICENSE) for full details.

---

## 🎬 Demo

![Branch Name Validation](demos/gifs/devrules-branch-name-validation.gif)

## 🚀 Features

- ✅ **Branch naming validation** - Enforce consistent branch naming conventions
- ✅ **Commit message format checking** - Validate commit message structure with GPG signing support
- ✅ **Pull Request validation** - Check PR size and title format
- ✅ **Deployment workflow** - Manage deployments across environments with Jenkins integration
- ⚙️ **Configurable via TOML** - Customize all rules to match your workflow
- 🔌 **Git hooks integration** - Automatic validation with pre-commit support
- 🎨 **Interactive mode with Gum** - Beautiful terminal UI with arrow-key selection and styled prompts
- 🌐 **GitHub API integration** - Manage issues, projects, and PRs directly
- 📊 **TUI Dashboard** - Interactive terminal dashboard for metrics and issue tracking
- 🏢 **Enterprise builds** - Create custom packages with embedded corporate configuration

## 📦 Installation
```bash
pip install devrules
```

### Optional: Install Gum for Enhanced UI

DevRules integrates with [Gum](https://github.com/charmbracelet/gum) for a beautiful interactive terminal experience. Install it for:
- Arrow-key selection menus
- Styled input prompts
- Formatted tables
- Colorful output

```bash
# macOS
brew install gum

# Linux (Debian/Ubuntu)
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list
sudo apt update && sudo apt install gum

# Windows (Scoop)
scoop install charm-gum
```

> **Note:** Gum is optional. DevRules falls back to standard prompts if Gum is not installed.

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
devrules check-pr 42 --owner your-org --repo your-repo
# Or configure owner/repo in .devrules.toml and just run:
devrules check-pr 42
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

8. **Manage GitHub Issues:**
```bash
# List issues from a project
devrules list-issues --project 6

# View issue details
devrules describe-issue 123

# Update issue status
devrules update-issue-status 123 --status "In Progress" --project 6
```

9. **Commit with validation:**
```bash
devrules commit "[FTR] Add new feature"
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

[github]
owner = "your-org"
repo = "your-repo"
```

For a complete configuration example, run `devrules init-config`.

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
| `create-branch` | `nb` | Create new branch (interactive with Gum) |
| `commit` | `ci` | Commit with validation |
| `icommit` | `ic` | Interactive commit with tag selection |
| `create-pr` | `pr` | Create pull request |
| `ipr` | - | Interactive PR with target selection |
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

## 🏢 Enterprise Builds

Create custom packages with embedded corporate configuration:

```bash
# Install enterprise dependencies
pip install "devrules[enterprise]"

# Build enterprise package
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --name devrules-mycompany \
  --sensitive github.api_url,github.owner
```

See [Enterprise Build Guide](docs/ENTERPRISE_BUILD.md) for more details.

## 📚 Documentation

For full documentation, visit [GitHub](https://github.com/pedroifgonzalez/devrules).

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🙏 Acknowledgments

Built with:
- [Typer](https://typer.tiangolo.com/) - Amazing CLI framework
- [Gum](https://github.com/charmbracelet/gum) - Glamorous shell scripts and terminal UI

## 📧 Contact

- GitHub: [@pedroifgonzalez](https://github.com/pedroifgonzalez)
- Email: pedroifgonzalez@gmail.com

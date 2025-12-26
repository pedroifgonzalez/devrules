# Git Hooks Integration Guide

## Overview

DevRules provides comprehensive Git hooks integration to enforce development standards automatically, regardless of whether developers use CLI or GUI interfaces.

## Installation

### Quick Setup
```bash
# Install all hooks at once
devrules install-hooks

# Remove all hooks
devrules uninstall-hooks
```

## Available Hooks

### 1. Commit Message Hook (`commit-msg`)
Validates commit message format and integrates with pre-commit.

**Validations:**
- Message format compliance
- Required tags/prefixes
- Length restrictions
- Issue number appending

**Configuration:**
```toml
[commit]
tags = ["feat", "fix", "docs", "refactor", "test"]
min_length = 10
max_length = 100
append_issue_number = true
```

### 2. Pre-commit Hook (`pre-commit`)
Validates files and repository state before commit.

**Validations:**
- Forbidden file patterns
- Repository state (uncommitted changes, behind remote)
- Documentation requirements

**Configuration:**
```toml
[commit]
forbidden_patterns = ["*.tmp", "secrets/*"]
forbidden_paths = [".env", "config/local.py"]

[validation]
check_uncommitted = true
check_behind_remote = true
warn_only = false
```

### 3. Pre-push Hook (`pre-push`)
Validates branch and issue status before push.

**Validations:**
- Branch naming conventions
- Branch ownership restrictions
- Protected branch prevention

**Configuration:**
```toml
[branch]
pattern = "^(feature|bugfix|hotfix)/[a-z0-9-]+$"
enforce_single_branch_per_issue_env = true

[commit]
protected_branch_prefixes = ["staging-", "release/"]
restrict_branch_to_owner = true
```

### 4. Post-checkout Hook (`post-checkout`)
Shows branch context after checkout.

**Features:**
- Branch type information
- Ownership status
- Relevant documentation links

## Enterprise Usage

### Team Configuration
Create team-specific configs:

```toml
# .devrules.frontend.toml
[branch]
pattern = "^(ui|feature|fix)/[a-z0-9-]+$"

[commit]
tags = ["ui", "feat", "fix", "refactor", "test"]

# .devrules.backend.toml  
[branch]
pattern = "^(api|feature|fix)/[a-z0-9-]+$"

[commit]
tags = ["api", "feat", "fix", "refactor", "test"]
```

### CI/CD Integration
```yaml
# .github/workflows/devrules.yml
name: DevRules Validation
on: [push, pull_request]

jobs:
  devrules:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install DevRules
        run: pip install devrules
      - name: Validate PR
        run: devrules check-pr ${{ github.event.number }}
```

## Hook Commands

### Manual Testing
```bash
# Test individual validations
devrules pre-commit-check
devrules pre-push-check --branch feature/new-ui
devrules branch-context --branch main

# Validate specific files
devrules check-commit .git/COMMIT_EDITMSG
devrules check-branch feature/new-ui
```

### Bypassing Hooks
```bash
# Bypass all hooks (if allowed by config)
git commit --no-verify -m "message"

# Check if bypass is allowed
grep allow_hook_bypass .devrules.toml
```

## Troubleshooting

### Hook Not Executing
```bash
# Check hook permissions
ls -la .git/hooks/

# Make executable
chmod +x .git/hooks/pre-commit
```

### Hook Fails Silently
```bash
# Test hook manually
.git/hooks/pre-commit

# Check hook logs
git config --global core.hooksPath .git/hooks
```

### Conflicts with Pre-commit
DevRules hooks are designed to work alongside pre-commit:
1. DevRules validates first
2. If DevRules passes, pre-commit runs
3. Either failure blocks the operation

## Best Practices

### 1. Gradual Adoption
```toml
[validation]
warn_only = true  # Start with warnings only
```

### 2. Team Onboarding
```bash
# Setup script for new developers
#!/bin/bash
pip install devrules
devrules init-config
devrules install-hooks
echo "DevRules configured! Check .devrules.toml for settings."
```

### 3. Monitoring
Track hook effectiveness:
```bash
# Count violations prevented
git log --grep="feat\|fix" --oneline | wc -l
```

## Migration from Other Tools

### From Husky (Node.js)
```bash
# Remove husky
npm uninstall husky

# Install DevRules
pip install devrules
devrules install-hooks
```

### From Manual Scripts
Replace manual hook scripts with DevRules commands:
```bash
# Old .git/hooks/pre-commit
#!/bin/bash
./scripts/lint.sh
./scripts/test.sh

# New (handled by DevRules)
devrules install-hooks  # Handles everything automatically
```

## Support

For issues with Git hooks:
1. Check `.devrules.toml` configuration
2. Verify hook permissions
3. Test commands manually
4. Review this guide and documentation

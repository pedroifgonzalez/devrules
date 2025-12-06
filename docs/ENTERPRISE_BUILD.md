# Enterprise Build Guide

This guide explains how to create and distribute enterprise builds of DevRules with embedded corporate configuration.

## Overview

Enterprise builds allow organizations to:
- Embed corporate development standards
- Encrypt sensitive information (URLs, tokens, etc.)
- Distribute as a standard Python package
- Ensure automatic compliance across teams
- Prevent user overrides of corporate policies

## Prerequisites

Install DevRules with enterprise support:

```bash
pip install devrules[enterprise]
```

Or for development:

```bash
uv pip install -e ".[enterprise]"
```

## Quick Start

### 1. Create Enterprise Configuration

Copy the example template:

```bash
cp .devrules.enterprise.toml.example .devrules.enterprise.toml
```

Edit `.devrules.enterprise.toml` with your corporate standards:

```toml
[enterprise]
enabled = true
locked = true  # Prevents user overrides
integrity_check = true

[enterprise.encryption]
sensitive_fields = [
    "github.api_url",
    "github.owner",
]

[branch]
pattern = "^(feature|bugfix|hotfix)/(JIRA-\\d+)-[a-z0-9-]+"
require_issue_number = true

[github]
api_url = "https://github.enterprise.company.com/api/v3"
owner = "company-org"
```

### 2. Build Enterprise Package

```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --name devrules-mycompany \
  --sensitive github.api_url,github.owner
```

This creates:
- `dist/devrules_mycompany-*.whl` - Installable package
- `dist/encryption.key` - Encryption key (keep secure!)
- `dist/DISTRIBUTION_README.md` - Installation instructions

### 3. Distribute Package

See [Enterprise Distribution Guide](ENTERPRISE_DISTRIBUTION.md) for distribution options.

## Build Command Reference

### Basic Usage

```bash
devrules build-enterprise --config <config-file>
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config`, `-c` | Path to enterprise config file | Required |
| `--output`, `-o` | Output directory | `dist` |
| `--name`, `-n` | Custom package name | `devrules-enterprise` |
| `--encrypt/--no-encrypt` | Encrypt sensitive fields | `True` |
| `--sensitive` | Comma-separated fields to encrypt | From config |
| `--suffix` | Version suffix | `enterprise` |
| `--keep-config` | Keep embedded config after build | `False` |

### Examples

**Basic enterprise build:**
```bash
devrules build-enterprise --config .devrules.enterprise.toml
```

**Custom package name:**
```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --name devrules-acme
```

**Specify sensitive fields:**
```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --sensitive github.api_url,github.owner,github.repo
```

**Build without encryption (not recommended):**
```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --no-encrypt
```

## Configuration Structure

### Enterprise Section

```toml
[enterprise]
enabled = true           # Enable enterprise mode
locked = true            # Lock configuration (prevent user overrides)
integrity_check = true   # Enable tampering detection
```

### Encryption Settings

```toml
[enterprise.encryption]
sensitive_fields = [
    "github.api_url",    # Dot notation for nested fields
    "github.owner",
    "github.repo",
    "jenkins.url",
    "jenkins.token",
]
```

### Standard Sections

All standard DevRules configuration sections are supported:
- `[branch]` - Branch naming rules
- `[commit]` - Commit message rules
- `[pr]` - Pull request rules
- `[github]` - GitHub integration

See [main README](../README.md) for configuration details.

## Encryption

### How It Works

1. **Selective Encryption**: Only specified fields are encrypted
2. **Symmetric Encryption**: Uses Fernet (AES-128) encryption
3. **Key Management**: Key saved to `dist/encryption.key`
4. **Transparent Decryption**: Automatic decryption on load

### Security Best Practices

#### ✅ DO:
- Use environment variables for keys in production
- Store keys in secure key management systems
- Rotate encryption keys periodically
- Limit access to encryption keys
- Use different keys for different environments

#### ❌ DON'T:
- Commit encryption keys to version control
- Share keys via email or chat
- Embed keys in CI/CD logs
- Use the same key across multiple organizations

### Environment Variable Setup

Instead of distributing the encryption key file:

```bash
# Set environment variable
export DEVRULES_ENTERPRISE_KEY=$(cat dist/encryption.key)

# Or in .bashrc / .zshrc
echo 'export DEVRULES_ENTERPRISE_KEY="<key-content>"' >> ~/.bashrc
```

Users can then install the package without needing the key file.

## Integrity Verification

Enterprise builds include SHA-256 hash verification to detect tampering.

### How It Works

1. Hash generated during build
2. Stored in `.integrity.hash` file
3. Verified on every config load
4. Warning displayed if verification fails

### Tampering Detection

If configuration is modified after build:

```
⚠️  Warning: Enterprise configuration integrity check failed!
   The configuration may have been tampered with.
```

This helps ensure corporate standards remain intact.

## Configuration Priority

When enterprise mode is enabled:

1. **ENTERPRISE** (Highest) - Embedded corporate config
2. **USER** - Local `.devrules.toml` (ignored if locked)
3. **DEFAULT** (Lowest) - Built-in defaults

### Locked vs Unlocked

**Locked (`locked = true`):**
- User `.devrules.toml` files are ignored
- Corporate standards cannot be overridden
- Recommended for strict compliance

**Unlocked (`locked = false`):**
- User configs can extend corporate config
- Corporate values take precedence on conflicts
- Useful for flexible environments

## Troubleshooting

### Build Fails

**Error: `pyproject.toml not found`**
- Solution: Run from project root directory

**Error: `Configuration file not found`**
- Solution: Check path to enterprise config file

### Encryption Issues

**Error: `Encryption key not set`**
- Solution: Set `DEVRULES_ENTERPRISE_KEY` environment variable

**Warning: `Unable to decrypt field`**
- Solution: Verify encryption key matches the one used during build

### Integrity Failures

**Warning: `Integrity check failed`**
- Cause: Configuration was modified after build
- Solution: Rebuild package or investigate tampering

## Advanced Topics

### Custom Version Suffix

```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --suffix internal-v2
```

Creates version like `0.1.3-internal-v2`

### Debugging

Keep embedded config for inspection:

```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --keep-config
```

Config will remain in `src/devrules/enterprise/` after build.

### Multiple Environments

Create different configs for each environment:

```bash
# Production
devrules build-enterprise \
  --config .devrules.enterprise.prod.toml \
  --name devrules-company-prod

# Staging
devrules build-enterprise \
  --config .devrules.enterprise.staging.toml \
  --name devrules-company-staging
```

## Next Steps

- [Distribution Guide](ENTERPRISE_DISTRIBUTION.md) - How to distribute your build
- [Migration Guide](../README.md) - Migrating existing projects
- [Security Best Practices](#security-best-practices) - Securing your deployment

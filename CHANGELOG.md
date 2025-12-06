# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2025-12-06

### Added
- **GPG commit signing** - New `gpg_sign` config option to auto-sign commits
- **Protected branches** - New `protected_branch_prefixes` to block direct commits on staging/integration branches
- **Git hooks installation** - `install-hooks` and `uninstall-hooks` commands for automatic commit validation
- **Pre-commit integration** - Git hooks now chain to pre-commit if installed
- **Command aliases** - Short aliases for all commands (e.g., `cb`, `ci`, `nb`, `li`)
- **Enterprise build improvements** - PEP 440 compliant versioning with `+` suffix

### Changed
- `init-config` now generates complete configuration with all available options
- Updated README with comprehensive documentation

### Fixed
- Enterprise build version format now uses PEP 440 local version identifier (`+enterprise` instead of `-enterprise`)
- Branch name sanitization removes special characters properly

## [0.1.3] - 2025-11-16

### Added
- CLI commands: commit

### Fixed
- Align internal `__version__` constants with project metadata version

## [0.1.2] - 2025-11-15

### Added
- Initial release
- Branch name validation with configurable patterns
- Commit message format validation
- Pull Request size and title validation
- Interactive branch creation command
- TOML-based configuration system
- Git hooks support
- CLI commands: check-branch, check-commit, check-pr, create-branch, init-config

### Features
- Configurable via .devrules.toml file
- Support for custom branch prefixes and naming patterns
- Customizable commit tags
- PR size limits (LOC and file count)
- GitHub API integration for PR validation
- Colorful CLI output with Typer

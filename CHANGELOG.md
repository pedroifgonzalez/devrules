# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

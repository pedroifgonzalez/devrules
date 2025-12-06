# Enterprise Distribution Guide

This guide covers how to distribute enterprise builds of DevRules to your organization.

## Distribution Options

### 1. Private PyPI Server

**Best for:** Large organizations with existing PyPI infrastructure

#### Setup

Use a private PyPI server like:
- [devpi](https://devpi.net/)
- [PyPI Server](https://pypi.org/project/pypiserver/)
- [Artifactory](https://jfrog.com/artifactory/)
- [Nexus Repository](https://www.sonatype.com/products/repository-oss)

#### Upload Package

```bash
# Build package
devrules build-enterprise --config .devrules.enterprise.toml --name devrules-company

# Upload to private PyPI
twine upload --repository-url https://pypi.company.com dist/devrules_company-*.whl
```

#### Install from Private PyPI

```bash
pip install devrules-company --index-url https://pypi.company.com/simple/
```

Or in `pyproject.toml`:

```toml
[[tool.uv.index]]
name = "company-pypi"
url = "https://pypi.company.com/simple/"

[project]
dependencies = [
    "devrules-company>=0.1.0",
]
```

---

### 2. Internal Git Repository

**Best for:** Organizations using Git-based package management

#### Setup

1. Create internal repository:
```bash
git init devrules-company-dist
cd devrules-company-dist
```

2. Add built package:
```bash
cp ../devrules/dist/devrules_company-*.whl .
git add .
git commit -m "Add devrules enterprise build"
git push origin main
```

#### Install from Git

```bash
pip install git+https://github.company.com/devops/devrules-company-dist.git
```

Or in `requirements.txt`:
```
devrules-company @ git+https://github.company.com/devops/devrules-company-dist.git
```

---

### 3. Direct Wheel Distribution

**Best for:** Small teams or simple deployments

#### Distribute

Share the wheel file via:
- Shared network drive
- Internal file server
- Cloud storage (S3, GCS, Azure Blob)

#### Install from Wheel

```bash
pip install /path/to/devrules_company-0.1.3+enterprise-py3-none-any.whl
```

Or from URL:
```bash
pip install https://files.company.com/packages/devrules_company-0.1.3+enterprise-py3-none-any.whl
```

---

### 4. Container Registry

**Best for:** Containerized environments

#### Create Docker Image

```dockerfile
FROM python:3.11-slim

# Copy wheel file
COPY dist/devrules_company-*.whl /tmp/

# Install package
RUN pip install /tmp/devrules_company-*.whl

# Set encryption key (if needed)
ENV DEVRULES_ENTERPRISE_KEY="your-encryption-key"

ENTRYPOINT ["devrules"]
```

Build and push:
```bash
docker build -t registry.company.com/devrules-company:latest .
docker push registry.company.com/devrules-company:latest
```

---

## Encryption Key Distribution

### Option 1: Environment Variables (Recommended)

**Setup on user machines:**

```bash
# Linux/Mac
echo 'export DEVRULES_ENTERPRISE_KEY="<key>"' >> ~/.bashrc
source ~/.bashrc

# Windows (PowerShell)
[Environment]::SetEnvironmentVariable("DEVRULES_ENTERPRISE_KEY", "<key>", "User")
```

**Setup in CI/CD:**

```yaml
# GitHub Actions
env:
  DEVRULES_ENTERPRISE_KEY: ${{ secrets.DEVRULES_KEY }}

# GitLab CI
variables:
  DEVRULES_ENTERPRISE_KEY: $DEVRULES_KEY

# Jenkins
environment {
  DEVRULES_ENTERPRISE_KEY = credentials('devrules-key')
}
```

### Option 2: Key Management Service

**AWS Secrets Manager:**

```python
import boto3

def get_devrules_key():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='devrules-enterprise-key')
    return response['SecretString']

os.environ['DEVRULES_ENTERPRISE_KEY'] = get_devrules_key()
```

**HashiCorp Vault:**

```bash
export DEVRULES_ENTERPRISE_KEY=$(vault kv get -field=key secret/devrules)
```

### Option 3: Embedded Key (Less Secure)

Include key in package distribution (not recommended for production):

```bash
# Include key in distribution
cp dist/encryption.key /path/to/shared/location/
```

---

## Version Management

### Semantic Versioning

Use semantic versioning with enterprise local version identifier (PEP 440):

```
0.1.3+enterprise       # Initial enterprise build
0.1.4+enterprise       # Bug fix
0.2.0+enterprise       # New features
1.0.0+enterprise       # Major release
```

### Multiple Versions

Maintain multiple versions for different environments:

```bash
# Production
devrules build-enterprise \
  --config .devrules.enterprise.prod.toml \
  --name devrules-company \
  --suffix prod

# Staging
devrules build-enterprise \
  --config .devrules.enterprise.staging.toml \
  --name devrules-company \
  --suffix staging
```

Install specific version:
```bash
pip install devrules-company==0.1.3-prod
pip install devrules-company==0.1.3-staging
```

---

## Update Procedures

### 1. Update Configuration

Edit enterprise config:
```bash
vim .devrules.enterprise.toml
```

### 2. Rebuild Package

```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --name devrules-company
```

### 3. Test Build

```bash
# Install in test environment
pip install dist/devrules_company-*.whl

# Verify configuration
devrules check-branch feature/123-test
```

### 4. Distribute Update

Upload to distribution channel:
```bash
twine upload --repository-url https://pypi.company.com dist/devrules_company-*.whl
```

### 5. Notify Teams

Send update notification:
```
Subject: DevRules Update - v0.1.4+enterprise

Changes:
- Updated branch naming pattern
- Added new commit tags
- Fixed PR validation

To update:
pip install --upgrade devrules-company
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Validate with DevRules

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install DevRules
        run: |
          pip install devrules-company --index-url https://pypi.company.com/simple/
        env:
          DEVRULES_ENTERPRISE_KEY: ${{ secrets.DEVRULES_KEY }}
      
      - name: Validate branch name
        run: devrules check-branch ${{ github.ref_name }}
      
      - name: Validate commits
        run: |
          git log --format=%B -n 1 > /tmp/commit.msg
          devrules check-commit /tmp/commit.msg
```

### GitLab CI

```yaml
validate:
  stage: test
  script:
    - pip install devrules-company --index-url https://pypi.company.com/simple/
    - devrules check-branch $CI_COMMIT_REF_NAME
    - git log --format=%B -n 1 > /tmp/commit.msg
    - devrules check-commit /tmp/commit.msg
  variables:
    DEVRULES_ENTERPRISE_KEY: $DEVRULES_KEY
```

### Jenkins

```groovy
pipeline {
    agent any
    
    environment {
        DEVRULES_ENTERPRISE_KEY = credentials('devrules-key')
    }
    
    stages {
        stage('Install DevRules') {
            steps {
                sh 'pip install devrules-company --index-url https://pypi.company.com/simple/'
            }
        }
        
        stage('Validate') {
            steps {
                sh 'devrules check-branch ${BRANCH_NAME}'
                sh 'git log --format=%B -n 1 > /tmp/commit.msg'
                sh 'devrules check-commit /tmp/commit.msg'
            }
        }
    }
}
```

---

## Pre-commit Hooks

Distribute pre-commit configuration:

**.pre-commit-config.yaml:**

```yaml
repos:
  - repo: local
    hooks:
      - id: devrules-commit
        name: DevRules Commit Validation
        entry: devrules check-commit
        language: system
        stages: [commit-msg]
```

Install on developer machines:
```bash
pip install devrules-company pre-commit
pre-commit install --hook-type commit-msg
```

---

## Monitoring and Compliance

### Usage Tracking

Track DevRules usage across teams:

```python
# Custom wrapper script
import subprocess
import logging

logging.basicConfig(filename='/var/log/devrules.log')

def track_usage(command):
    logging.info(f"DevRules command: {command}")
    subprocess.run(['devrules'] + command)

# Usage
track_usage(['check-branch', 'feature/123-test'])
```

### Compliance Reports

Generate compliance reports:

```bash
# Check all branches
for branch in $(git branch -r); do
    devrules check-branch $branch || echo "$branch: FAILED"
done > compliance-report.txt
```

---

## Troubleshooting

### Installation Issues

**Error: Package not found**
- Verify PyPI URL is correct
- Check network connectivity
- Ensure authentication credentials are set

**Error: Permission denied**
- Check file permissions on wheel file
- Verify user has install permissions

### Runtime Issues

**Error: Encryption key not set**
- Set `DEVRULES_ENTERPRISE_KEY` environment variable
- Verify key is correct

**Warning: Integrity check failed**
- Package may have been tampered with
- Reinstall from trusted source

---

## Best Practices

### Security
- ✅ Use environment variables for encryption keys
- ✅ Rotate keys periodically
- ✅ Limit access to distribution channels
- ✅ Enable integrity checking
- ❌ Don't commit keys to version control
- ❌ Don't share keys via insecure channels

### Distribution
- ✅ Use semantic versioning
- ✅ Test builds before distribution
- ✅ Maintain changelog
- ✅ Document breaking changes
- ❌ Don't skip testing
- ❌ Don't force-update without notice

### Maintenance
- ✅ Regular updates for security patches
- ✅ Monitor usage and feedback
- ✅ Keep documentation current
- ✅ Provide support channels
- ❌ Don't ignore user feedback
- ❌ Don't leave deprecated versions active

---

## Support

For issues or questions:
- Internal wiki: `https://wiki.company.com/devrules`
- Slack channel: `#devrules-support`
- Email: `devops@company.com`

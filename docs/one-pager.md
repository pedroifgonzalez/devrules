# ⚙️ DevRules

*Automate your internal rules. Reduce errors. Accelerate onboarding.*

---

## 🧩 The Problem

Every company has rules. But few apply them automatically.

- ❌ New employees unintentionally break conventions
- ❌ Scattered or outdated documentation
- ❌ Common conflicts:
  - Commits to main 🤦
  - Poorly named branches
  - Mixed changes between features
  - Inconsistent commit messages
- ❌ Tribal knowledge: doesn't scale, isn't taught, isn't preserved
- ❌ Manual PR reviews catch issues too late

## 🚀 The Solution: DevRules

Your standards, converted into living rules, applied directly in the developer's workflow.

**DevRules = Linting + Corporate rules + Automatic onboarding**

- Installs as a Python CLI tool
- Uses a secure, versioned, and customizable `.devrules.toml` file
- Applies rules automatically through Git hooks when developers:
  - Create a branch
  - Make a commit
  - Open a pull request
  - Deploy to environments
- Provides interactive tools for guided workflows
- Integrates with GitHub API for seamless issue and PR management

## ⭐ Key Benefits

- **🏗️ Automatic standardization**  
  Everyone follows the same rules without memorizing anything.

- **🚦 Real-time error prevention**  
  Detects and blocks bad practices before they reach the repo.

- **🧠 Accelerated onboarding**  
  New hires learn the rules by doing, not reading.

- **🛡️ Corporate compliance**  
  Security, style, architecture, naming, and processes… all enforced.

- **⚡ Less rework and more speed**  
  Fewer conflicts → more time building features.

- **🎨 Interactive workflows**  
  Guided branch creation and commit processes reduce cognitive load.

- **📚 Context-aware documentation**  
  Documentation appears automatically when you modify specific files—perfect timing, 100% relevant, zero searching.

## 🔍 Real Examples

- **✔️ Prevent commits to forbidden branches**  
  Automatically blocks commits to `main`, `develop`, or staging branches.

- **✔️ Smart branch naming**  
  Validates and suggests branch names following your patterns:
  - `feature/1234-improve-cache`
  - `bugfix/998-login-error`
  - `hotfix/critical-security-patch`

- **✔️ Commit message validation**  
  Enforces structured commit messages with configurable tags:
  - `[FTR] Add user authentication`
  - `[FIX] Resolve memory leak in cache`
  - `[DOCS] Update API documentation`

- **✔️ Pull Request size control**  
  Prevents oversized PRs that are hard to review (configurable limits on lines of code and files changed).

- **✔️ Deployment workflow management**  
  Control deployments across environments with built-in checks and Jenkins integration.

- **✔️ Interactive TUI Dashboard**  
  Track metrics, manage issues, and monitor project health from your terminal.

- **✔️ GitHub integration**  
  Link branches to issues, create PRs, and update project boards automatically.

- **✔️ Enterprise builds**  
  Create custom packages with embedded corporate configuration for zero-config deployments.  
  Companies can build their own branded version (e.g., `devrules-acme`) with pre-configured rules baked in.

- **✔️ Context-aware documentation**  
  Automatically displays relevant documentation based on files you're modifying:
  - Shows migration guides when touching `migrations/**`
  - Displays API guidelines when editing `api/**/*.py`
  - Surfaces security policies for sensitive code
  - Includes actionable checklists, not just links
  - **300% increase in documentation visibility** - appears exactly when needed, not before or after

## 📈 Company Impact

| Current problem | With DevRules |
|----------------|--------------|
| New hires take weeks to adopt standards | ✅ They learn from the first commit |
| Rules are forgotten, violated, or reinterpreted | ✅ Living rules, always applied |
| Rework due to broken merges and workflows | ✅ Automatic prevention |
| Misaligned teams | ✅ Absolute consistency |
| Manual enforcement wastes senior time | ✅ Automated validation |
| Complex deployment procedures | ✅ Standardized deployment workflows |

## 🎯 Quick Wins

**Day 1:** Install and configure in under 5 minutes  
**Week 1:** All commits follow corporate standards  
**Month 1:** Onboarding time reduced by 50%  
**Quarter 1:** Measurable reduction in merge conflicts and PR rework

## 🏢 Enterprise Customization

**Build Your Own Branded Version**

Companies can create their own custom DevRules package with embedded corporate standards:

```bash
devrules build-enterprise \
  --config .devrules.enterprise.toml \
  --name devrules-mycompany \
  --sensitive github.api_url,github.owner
```

**Benefits:**
- 📦 **Zero-config deployment** - Developers install your package and rules are pre-loaded
- 🏷️ **Company branding** - `pip install devrules-acme` instead of generic DevRules
- 🔒 **Embedded secrets** - Safely include internal API endpoints and configurations
- 🎯 **Version control** - Lock your entire organization to specific rule versions
- 🚀 **Instant compliance** - New hires get all standards from day one

Perfect for organizations with strict compliance, security requirements, or complex internal workflows.

## 🎤 Final Message

DevRules allows you to operate with large company standards, without needing to build costly internal tooling.

**Reduce errors. Accelerate deliveries. Improve quality.**

Perfect for teams of any size—from startups establishing their first conventions to enterprises enforcing complex compliance requirements.

---

### 🚀 Start today

```bash
pip install devrules
```

**Initialize your configuration:**
```bash
devrules init-config
```

**Install Git hooks for automatic enforcement:**
```bash
devrules install-hooks
```

**Create your first compliant branch:**
```bash
devrules create-branch
```

---

[📖 View documentation](https://github.com/pedroifgonzalez/devrules) · [💬 Contact](mailto:pedroifgonzalez@gmail.com) · [🐙 GitHub](https://github.com/pedroifgonzalez/devrules)
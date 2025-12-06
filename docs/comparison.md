# 🆚 DevRules vs Other Tools

## Overview

This document compares DevRules with popular development tools to help you understand where DevRules adds unique value in your development workflow.

---

## 🆚 GitHub Branch Creation vs DevRules

### What GitHub Offers

GitHub provides:
- "Create branch from issue" button
- Automatic naming based on issue title
- Base branch suggestions

### What GitHub Cannot Do

| Problem | GitHub Web | DevRules |
|---------|-----------|----------|
| Prevent creating branches from wrong base (e.g., `feature/other-task`) | ❌ No | ✅ Yes, rules block the action |
| Verify developer has updated local repo before creating branch | ❌ No | ✅ Yes |
| Verify no uncommitted changes before creating new branch | ❌ No | ✅ Yes |
| Enforce strict corporate naming (e.g., `feat/<ID>-<slug>`) | ⚠️ Partial | ✅ 100% enforced |
| Custom rules per company (architecture, CI, processes) | ❌ No | ✅ Fully customizable |
| Automatically show internal guides during development | ❌ No | ✅ Yes |
| Work consistently in terminal, VSCode, PyCharm, etc. | ❌ No | ✅ Yes |
| Function offline | ❌ No | ✅ Yes |
| Integrate branch, commit, PR, and CI standards in one place | ❌ No | ✅ Yes |

### Conclusion

**GitHub** only controls visual/descriptive aspects, but doesn't control the real local workflow where errors that cost time and money occur.

**DevRules** controls user behavior before the failure happens.

---

## 🆚 GitHub Pull Requests vs DevRules

### What GitHub Offers

GitHub provides:
- PR templates
- Review rules
- Draft PRs
- Branch protections

### Where GitHub Falls Short

| Problem | GitHub | DevRules |
|---------|--------|----------|
| Prevent PR to wrong branch (e.g., main instead of develop) | ❌ No | ✅ Yes, blocks push before PR |
| Detect if you forgot to update entrypoint when touching migrations | ❌ No | ✅ Yes |
| Automatically show correct internal checklist based on files changed | ❌ No | ✅ Yes |
| Prevent pushing commits with forbidden files (local configs, dumps, etc.) | ❌ No | ✅ Yes |
| Verify you ran tests locally before PR | ❌ No | ✅ Yes |
| Enforce mandatory corporate policies | ❌ No | ✅ Yes |
| Link documentation based on modified folder | ❌ No | ✅ Yes |

### Conclusion

**GitHub** helps after you push.  
**DevRules** intervenes before you make the mistake.

---

## 🆚 GitHub Actions / GitLab CI vs DevRules

CI/CD pipelines detect errors but too late—when they're already in the repo.

| Problem | CI/CD | DevRules |
|---------|-------|----------|
| Prevent developer from pushing migrations without review | ❌ No | ✅ Yes |
| Detect naming or structure conflicts before push | ❌ No | ✅ Yes |
| Educate new developers on how things are done | ❌ 0% | ✅ High impact |
| Prevent work on protected branches before push | ❌ No | ✅ Yes |
| Show internal guides only when relevant | ❌ No | ✅ Yes |
| Control best practices at local level | ❌ No | ✅ Yes |

### Key Difference

**CI/CD** catches problems after commit and push (expensive feedback loop).  
**DevRules** prevents problems before commit (instant feedback).

---

## 🆚 Static Documentation vs DevRules

### Traditional Internal Documentation

- Static and disconnected from workflow
- Nobody reads it
- Quickly becomes outdated
- Doesn't appear automatically at the right moment
- No enforcement

### DevRules Approach

- Activates information contextually
- Shows exactly what you need based on folder, file, or action
- Prevents documentation from being forgotten
- Enforces standards as documentation is accessed
- Living documentation that evolves with your codebase

---

## 🆚 Pre-commit Hooks vs DevRules

### What Pre-commit Offers

- File formatting (black, prettier, etc.)
- Linting (eslint, flake8, etc.)
- Generic checks (trailing whitespace, YAML validation)

### What DevRules Adds

| Capability | Pre-commit | DevRules |
|------------|-----------|----------|
| Code formatting and linting | ✅ Yes | ⚠️ Not the focus |
| Branch naming validation | ❌ No | ✅ Yes |
| Commit message structure enforcement | ⚠️ Basic | ✅ Advanced with tags |
| Pull request size control | ❌ No | ✅ Yes |
| Deployment workflow management | ❌ No | ✅ Yes |
| Interactive branch creation | ❌ No | ✅ Yes |
| GitHub issue integration | ❌ No | ✅ Yes |
| Context-aware documentation | ❌ No | ✅ Yes |
| Corporate compliance rules | ❌ No | ✅ Yes |
| TUI dashboard for metrics | ❌ No | ✅ Yes |

### Complementary Tools

DevRules **complements** pre-commit hooks—they solve different problems:
- **Pre-commit**: Code quality and formatting
- **DevRules**: Workflow, process, and corporate standards

Use them together for comprehensive quality control!

---

## 🆚 Visual Comparison: Interface vs Behavior

| Aspect | Visual Tools (GitHub, GitLab) | DevRules |
|--------|------------------------------|----------|
| "Pretty clicks" | ✅ Yes | ⚠️ Not the focus |
| Real workflow control | ❌ No | ✅ Yes |
| Error prevention | ⚠️ Partial | ✅ Strong |
| Adapted to internal company rules | ❌ No | ✅ Yes |
| Educational | ❌ No | ✅ Yes |
| Standards automation | ❌ No | ✅ Yes |
| Runs locally | ❌ No | ✅ Yes |
| Prevents errors before push | ❌ No | ✅ Yes |
| Reduces rework | ⚠️ Partial | ✅ Significantly |

---

## 💡 When to Use What

### Use GitHub/GitLab for:
- Code hosting and version control
- Team collaboration and code review
- CI/CD automation
- Issue and project tracking
- Visual PR management

### Use DevRules for:
- Enforcing corporate development standards
- Preventing errors before they reach the repo
- Accelerating developer onboarding
- Maintaining consistency across teams
- Integrating custom business rules into developer workflow
- Context-aware documentation and guidance

### Use Both Together:
DevRules doesn't replace GitHub or GitLab—it **enhances** your existing workflow by adding a critical layer of local enforcement and guidance that these platforms cannot provide.

---

## 🎯 The DevRules Advantage

### Prevention Over Detection

Most tools operate in **detection mode**:
1. Developer makes mistake
2. Pushes to remote
3. CI fails or reviewer catches it
4. Developer must fix and re-push
5. **Time and productivity lost**

DevRules operates in **prevention mode**:
1. Developer attempts action
2. DevRules validates in real-time
3. Provides immediate feedback and guidance
4. Developer corrects before commit
5. **Time and productivity saved**

### The Cost of Late Detection

- **CI pipeline failure**: 5-15 minutes wasted
- **PR rejection**: 30+ minutes of context switching
- **Production incident**: Hours or days of emergency fixes
- **New hire mistakes**: Weeks of establishing good habits

### The Value of Early Prevention

- **Instant feedback**: < 1 second validation
- **Zero CI failures** from preventable issues
- **No PR rework** from standard violations
- **Day 1 compliance** for new hires
- **Context-aware documentation**: 300%+ increase in visibility—appears exactly when needed

### The Documentation Problem

**Traditional approach:**
- Developer needs to modify migrations
- Searches wiki/Confluence for "migration guidelines"
- Finds outdated documentation or multiple conflicting versions
- Asks in Slack, waits for response
- **15-30 minutes wasted**

**DevRules approach:**
1. Developer runs `git add migrations/003_new.py`
2. Developer runs `devrules commit "[FTR] Add migration"`
3. System automatically shows:
   - Migration guidelines URL
   - Relevant checklist items
   - Custom messages for this specific change
4. **0 minutes wasted, perfect timing, 100% relevant**

### Why Context-Aware Documentation Matters

- **Perfect Timing:** Shown during commit/PR, not weeks earlier in onboarding
- **100% Relevant:** Only displays docs for files actually being modified
- **Automatic:** No searching, no bookmarking, no remembering URLs
- **Actionable:** Includes checklists and steps, not just passive links
- **Educational:** New developers learn correct patterns by doing
- **Always Current:** Wiki links updated in one place (`.devrules.toml`)

---

## 📊 ROI Comparison

| Scenario | Without DevRules | With DevRules |
|----------|------------------|---------------|
| **New developer onboarding** | 2-4 weeks to learn standards | 3-5 days (learn by doing) |
| **Average PR iterations** | 2-3 rounds | 1-2 rounds |
| **CI failures from preventable issues** | 15-20% of runs | < 5% of runs |
| **Time spent on code review** | High (catching standard violations) | Low (focus on logic and design) |
| **Merge conflicts** | Frequent | Significantly reduced |
| **Documentation maintenance** | Manual, often outdated | Automated, always current |
| **Documentation access rate** | ~5% check docs before committing | 100% see relevant docs automatically |
| **Finding right documentation** | 10-15 min searching | 0 min (shown automatically) |

---

## 🚀 Summary

DevRules fills a critical gap in the development toolchain:

- **GitHub/GitLab**: Excellent for collaboration after code is written
- **CI/CD**: Great for automated testing after code is pushed
- **Pre-commit**: Perfect for code formatting before commit
- **DevRules**: Essential for enforcing process, workflow, and corporate standards in real-time

Together, these tools create a comprehensive quality control system that operates at every stage of development—from first keystroke to production deployment.
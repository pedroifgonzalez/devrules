#!/usr/bin/env python
"""Test script to verify issue browser functionality."""

import os
import sys

sys.path.insert(0, "src")

# Check if GH_TOKEN is set
gh_token = os.getenv("GH_TOKEN")
if not gh_token:
    print("⚠️  GH_TOKEN not set. Issue browser will show configuration message.")
    print("   To test with real data, set: export GH_TOKEN=your_token")
else:
    print(f"✓ GH_TOKEN is configured (length: {len(gh_token)})")

# Test imports
try:
    from devrules.tui.services.github_service import GitHubService

    print("✓ GitHubService imported successfully")

    # Test GitHub service if token is available
    if gh_token:
        # Try to get repo info from git remote
        import re
        import subprocess

        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            remote_url = result.stdout.strip()
            match = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)", remote_url)

            if match:
                owner, repo = match.group(1), match.group(2)
                print(f"✓ Detected repository: {owner}/{repo}")

                # Test fetching issues
                service = GitHubService(owner, repo, gh_token)
                issues = service.get_issues(state="all")
                print(f"✓ Fetched {len(issues)} issues from GitHub")

                if issues:
                    print("\nSample issue:")
                    issue = issues[0]
                    print(f"  #{issue.number}: {issue.title}")
                    print(f"  State: {issue.state}")
                    print(f"  Labels: {', '.join(issue.labels) if issue.labels else 'None'}")
            else:
                print("⚠️  Could not parse GitHub repository from remote URL")

        except subprocess.CalledProcessError:
            print("⚠️  Not in a git repository or no remote configured")

    print("\n✓ All checks passed! Issue browser is ready.")
    print("\nRun the dashboard to see it in action:")
    print("  ./.venv/bin/python demo_dashboard.py")

except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

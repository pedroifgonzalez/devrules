# DevRules TUI Dashboard

## Quick Start

The TUI dashboard is fully functional with metrics, branch explorer, and GitHub issue tracking!

### Installation

```bash
# Install with TUI dependencies
pip install -e ".[tui]"

# Or using uv
uv pip install -e ".[tui]"
```

### Running the Dashboard

```bash
# Using the CLI command
PYTHONPATH=src ./.venv/bin/python -m devrules.cli dashboard

# Or using the demo script
./.venv/bin/python demo_dashboard.py
```

### Features Implemented

#### ✅ Dashboard Tab
- **Branch Compliance**: Shows percentage of branches following naming conventions
- **Commit Quality**: Analyzes last 100 commits for message format compliance
- **Active Branches**: Total count of local branches
- Real-time metrics with progress bars

#### ✅ Issues Tab
- **GitHub Integration**: Fetches issues from your repository
- **Branch Matching**: Automatically links issues to branches
- **Filtering**: Filter by state (open/closed) or branch status (has/no branch)
- **Status Indicators**:
  - `✓` - Closed issue
  - `🔀` - Has branch
  - `○` - Open, no branch
- **Auto-detection**: Automatically detects repository from git remote

**Setup:**
```bash
# Set GitHub token
export GH_TOKEN=ghp_your_token_here

# Run dashboard
./.venv/bin/python demo_dashboard.py
```

#### ✅ Branches Tab
- Lists all local branches
- Shows validation status (✓/✗) for each branch
- Summary statistics (total, valid, invalid)
- Color-coded status indicators

### Keyboard Shortcuts

- `q` - Quit the dashboard
- `d` - Toggle dark mode
- `r` - Refresh data
- `Tab` / `Shift+Tab` - Switch between tabs
- Arrow keys - Navigate tables

### Next Steps

1. **Enhanced Metrics**: Add time-series graphs using plotext
2. **Quick Actions**: Branch creation from issues
3. **More Filters**: Search by assignee, labels, milestones
4. **PR Integration**: Show PR status for branches

## Architecture

```
src/devrules/tui/
├── __init__.py           # Package initialization
├── app.py                # Main Textual application
├── screens/              # Screen components
│   ├── dashboard.py      # Metrics dashboard ✓
│   ├── issues.py         # Issue browser ✓
│   └── branches.py       # Branch explorer ✓
├── widgets/              # Reusable widgets
│   └── metrics_card.py   # Metric display card ✓
└── services/             # Data services
    ├── metrics_service.py    # Git metrics analysis ✓
    └── github_service.py     # GitHub API integration ✓
```

## Testing

```bash
# Test TUI imports
./.venv/bin/python test_tui.py

# Test issue browser
./.venv/bin/python test_issues.py

# Run all tests
PYTHONPATH=src ./.venv/bin/pytest -v

# Run the dashboard
./.venv/bin/python demo_dashboard.py
```

## Troubleshooting

### Issue browser shows "GitHub token not configured"
Set the `GH_TOKEN` environment variable:
```bash
export GH_TOKEN=ghp_your_github_token
```

### Issue browser shows "Could not detect GitHub repository"
Make sure you're in a git repository with a GitHub remote:
```bash
git remote -v  # Should show github.com URL
```

### Dashboard shows import errors
Install TUI dependencies:
```bash
pip install -e ".[tui]"
```


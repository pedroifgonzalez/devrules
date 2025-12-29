"""Tests for TUI services."""

from devrules.tui.services.metrics_service import MetricsService


def test_metrics_service_initialization():
    """Test that MetricsService can be initialized."""
    service = MetricsService()
    assert service is not None
    assert service.config is not None


def test_get_all_branches():
    """Test getting all branches."""
    service = MetricsService()
    branches = service.get_all_branches()

    # Should return a list (may be empty if not in a git repo)
    assert isinstance(branches, list)


def test_analyze_branches():
    """Test branch analysis."""
    service = MetricsService()
    metrics = service.analyze_branches()

    # Check that metrics object has expected attributes
    assert hasattr(metrics, "total_branches")
    assert hasattr(metrics, "valid_branches")
    assert hasattr(metrics, "invalid_branches")
    assert hasattr(metrics, "compliance_percentage")
    assert hasattr(metrics, "invalid_branch_names")

    # Validate data types
    assert isinstance(metrics.total_branches, int)
    assert isinstance(metrics.valid_branches, int)
    assert isinstance(metrics.invalid_branches, int)
    assert isinstance(metrics.compliance_percentage, float)
    assert isinstance(metrics.invalid_branch_names, list)

    # Validate relationships
    assert metrics.total_branches == metrics.valid_branches + metrics.invalid_branches
    if metrics.total_branches > 0:
        assert 0 <= metrics.compliance_percentage <= 100


def test_get_recent_commits():
    """Test getting recent commits."""
    service = MetricsService()
    commits = service.get_recent_commits(limit=10)

    # Should return a list
    assert isinstance(commits, list)

    # If there are commits, they should be strings
    for commit in commits:
        assert isinstance(commit, str)


def test_analyze_commits():
    """Test commit analysis."""
    service = MetricsService()
    metrics = service.analyze_commits(limit=10)

    # Check that metrics object has expected attributes
    assert hasattr(metrics, "total_commits")
    assert hasattr(metrics, "valid_commits")
    assert hasattr(metrics, "invalid_commits")
    assert hasattr(metrics, "compliance_percentage")

    # Validate data types
    assert isinstance(metrics.total_commits, int)
    assert isinstance(metrics.valid_commits, int)
    assert isinstance(metrics.invalid_commits, int)
    assert isinstance(metrics.compliance_percentage, float)

    # Validate relationships
    assert metrics.total_commits == metrics.valid_commits + metrics.invalid_commits
    if metrics.total_commits > 0:
        assert 0 <= metrics.compliance_percentage <= 100


def test_get_repository_metrics():
    """Test getting comprehensive repository metrics."""
    service = MetricsService()
    repo_metrics = service.get_repository_metrics()

    # Check that it has both branch and commit metrics
    assert hasattr(repo_metrics, "branch_metrics")
    assert hasattr(repo_metrics, "commit_metrics")

    # Verify branch metrics
    assert hasattr(repo_metrics.branch_metrics, "total_branches")
    assert hasattr(repo_metrics.branch_metrics, "compliance_percentage")

    # Verify commit metrics
    assert hasattr(repo_metrics.commit_metrics, "total_commits")
    assert hasattr(repo_metrics.commit_metrics, "compliance_percentage")

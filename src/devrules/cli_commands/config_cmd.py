import os
import subprocess
from typing import Any, Callable, Dict

import typer


def register(app: typer.Typer) -> Dict[str, Callable[..., Any]]:
    @app.command()
    def init_config(
        path: str = typer.Option(".devrules.toml", "--path", "-p", help="Config file path"),
    ):
        """Generate example configuration file."""

        github_owner = "your-github-username"
        github_repo = "your-repo-name"
        project = "Example Project (#6)"

        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            url = result.stdout.strip()

            if "github.com" in url:
                if url.startswith("git@"):
                    path_part = url.split(":", 1)[1]
                else:
                    path_part = url.split("github.com", 1)[1].lstrip("/:")

                path_part = path_part.replace(".git", "")
                parts = path_part.split("/")

                if len(parts) >= 2:
                    github_owner = parts[-2]
                    github_repo = parts[-1]
        except Exception:
            pass

        example_config = """# DevRules Configuration File

[branch]
pattern = "^(feature|bugfix|hotfix|release|docs)/(\\\d+-)?[a-z0-9-]+"
prefixes = ["feature", "bugfix", "hotfix", "release", "docs"]
require_issue_number = false
enforce_single_branch_per_issue_env = true  # If true, only one branch per issue per environment (dev/staging)
labels_hierarchy = ["docs", "feature", "bugfix", "hotfix"]

[branch.labels_mapping]
enhancement = "feature"
bug = "bugfix"
documentation = "docs"

[commit]
tags = ["WIP", "FTR", "FIX", "DOCS", "TST", "REF"]
pattern = "^\\\[({tags})\\\].+"
min_length = 10
max_length = 100
restrict_branch_to_owner = true
append_issue_number = true
allow_hook_bypass = false  # If true, allows commits with --no-verify flag


[pr]
max_loc = 400
max_files = 20
require_title_tag = true
title_pattern = "^\\\[({tags})\\\].+"

[github]
api_url = "https://api.github.com"
timeout = 30
owner = "{github_owner}"  # GitHub repository owner
repo = "{github_repo}"          # GitHub repository name
valid_statuses = [
  "Backlog",
  "Blocked",
  "To Do",
  "In Progress",
  "Waiting Integration",
  "QA Testing",
  "QA In Progress",
  "QA Approved",
  "Pending To Deploy",
  "Done",
]

[github.projects]
project = "{project}"
""".format(
            github_owner=github_owner,
            github_repo=github_repo,
            project=project,
            tags="WIP|FTR|FIX|DOCS|TST|REF",
        )

        if os.path.exists(path):
            overwrite = typer.confirm(f"{path} already exists. Overwrite?")
            if not overwrite:
                typer.echo("Cancelled.")
                raise typer.Exit(code=0)

        with open(path, "w") as f:
            f.write(example_config)

        typer.secho(f"✔ Configuration file created: {path}", fg=typer.colors.GREEN)

    return {"init_config": init_config}

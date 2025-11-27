from dataclasses import dataclass
from typing import Optional

# {
#     "assignees": ["pedroifgonzalez"],
#     "content": {
#         "body": "",
#         "number": 12,
#         "repository": "pedroifgonzalez/devrules",
#         "title": "Allow create branch command to extract data from an issue and use it",
#         "type": "Issue",
#         "url": "https://github.com/pedroifgonzalez/devrules/issues/12",
#     },
#     "id": "PVTI_lAHOA1BrW84BI0aizghmmts",
#     "labels": ["enhancement"],
#     "repository": "https://github.com/pedroifgonzalez/devrules",
#     "status": "In progress",
#     "title": "Allow create branch command to extract data from an issue and use it",
# }


@dataclass
class ProjectItem:
    assignees: Optional[list[str]] = None
    content: Optional[dict] = None
    id: Optional[str] = None
    labels: Optional[list[str]] = None
    repository: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None


@dataclass
class PRInfo:
    """Pull request information."""

    additions: int
    deletions: int
    changed_files: int
    title: str

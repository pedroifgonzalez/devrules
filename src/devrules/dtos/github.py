from dataclasses import dataclass

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
    assignees: list[str] = None
    content: dict = None
    id: str = None
    labels: list[str] = None
    repository: str = None
    status: str = None
    title: str = None

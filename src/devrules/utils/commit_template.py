"""Utilities for commit message templates."""

import re

DEFAULT_COMMIT_TEMPLATE = "[{tag}] {message}"
DEFAULT_CONTEXT_TEMPLATE = "({context})"
SUPPORTED_TEMPLATE_FIELDS = {"tag", "prefix", "message", "context", "context_block"}


def uses_context(template: str) -> bool:
    """Return whether the template references context."""
    return "{context}" in template or "{context_block}" in template


def requires_context(template: str) -> bool:
    """Return whether the template requires a context value."""
    return "{context}" in template and "{context_block}" not in template


def format_commit_message(
    *,
    template: str,
    tag: str,
    message: str,
    context: str = "",
    context_template: str = DEFAULT_CONTEXT_TEMPLATE,
) -> str:
    """Render a commit message from a configured template."""
    context = context.strip()
    context_block = context_template.format(context=context) if context else ""

    try:
        return template.format(
            tag=tag,
            prefix=tag,
            message=message.strip(),
            context=context,
            context_block=context_block,
        ).strip()
    except KeyError as exc:
        raise ValueError(f"Unsupported commit template placeholder: {exc}") from exc


def build_commit_pattern(tags: list[str], template: str, context_template: str) -> str:
    """Build a validation regex from a commit template."""
    _validate_supported_placeholders(template)
    _validate_supported_placeholders(
        context_template, allow_message=False, allow_context_block=False
    )

    escaped = re.escape(template)
    context_block_pattern = _build_context_block_pattern(context_template)

    replacements = {
        r"\{tag\}": _build_tag_pattern(tags),
        r"\{prefix\}": _build_tag_pattern(tags),
        r"\{message\}": r"(?P<message>.+)",
        r"\{context\}": r"(?P<context>.+?)",
        r"\{context_block\}": rf"(?P<context_block>{context_block_pattern})?",
    }

    for placeholder, regex in replacements.items():
        escaped = escaped.replace(placeholder, regex)

    return f"^{escaped}$"


def build_commit_example(
    tags: list[str], template: str, context_template: str = DEFAULT_CONTEXT_TEMPLATE
) -> str:
    """Build a sample commit message from a template."""
    sample_tag = tags[0] if tags else "TAG"
    sample_context = "scope" if uses_context(template) else ""
    return format_commit_message(
        template=template,
        tag=sample_tag,
        message="Commit message",
        context=sample_context,
        context_template=context_template,
    )


def _build_tag_pattern(tags: list[str]) -> str:
    escaped_tags = [re.escape(str(tag)) for tag in tags]
    return rf"(?P<tag>{'|'.join(escaped_tags)})"


def _build_context_block_pattern(context_template: str) -> str:
    escaped = re.escape(context_template)
    return escaped.replace(r"\{context\}", r"(?P<context>.+?)")


def _validate_supported_placeholders(
    template: str, *, allow_message: bool = True, allow_context_block: bool = True
) -> None:
    placeholders = set(re.findall(r"{([a-zA-Z_]+)}", template))
    supported = set(SUPPORTED_TEMPLATE_FIELDS)
    if not allow_message:
        supported.discard("message")
    if not allow_context_block:
        supported.discard("context_block")

    invalid = placeholders - supported
    if invalid:
        supported_list = ", ".join(sorted(supported))
        raise ValueError(
            f"Unsupported commit template placeholders: {', '.join(sorted(invalid))}. "
            f"Supported placeholders: {supported_list}"
        )

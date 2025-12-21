import typer


def add_typer_block_message(
    header: str,
    subheader: str,
    messages: list[str],
    indent_block: bool = True,
    use_separator: bool = True,
):
    indent = " " * 4
    all_messages = []
    all_messages.append(header)
    all_messages.append(subheader)
    messages_output = [indent + message for message in messages] if indent_block else messages
    all_messages.extend(messages_output)
    extended_messages = []
    for message in all_messages:
        extended_messages.extend(message.split("\n"))
    longest_message = ""
    for m in extended_messages:
        if len(m) > len(longest_message):
            longest_message = m

    separator = "=" * len(longest_message)

    # center header
    diff = len(separator) - len(header)
    if diff % 2 != 0:
        separator += "="
        diff = len(separator) - len(header)
    space_to_add = " " * (diff // 2)
    centered_header = space_to_add + header + space_to_add

    typer.echo()
    if len(header) > 40 or not use_separator:
        typer.secho(header, fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho(separator, fg=typer.colors.GREEN)
        typer.secho(centered_header, fg=typer.colors.GREEN, bold=True)
        typer.secho(separator, fg=typer.colors.GREEN)
    typer.echo(f"\n{subheader}")
    for message in messages:
        output = message
        if indent_block:
            output = indent + output
        typer.echo(output)

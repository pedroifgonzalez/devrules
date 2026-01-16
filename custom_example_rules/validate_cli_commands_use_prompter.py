from devrules.core.rules_engine import rule


@rule(
    name="prompter_cli_validator",
    description="Validates cli commands use default prompter instead of typer or gum",
)
def valid_usage_of_auto_detected_prompter() -> tuple[bool, str]:
    import ast
    from pathlib import Path

    def _find_cli_commands_dir(start: Path) -> Path | None:
        current = start.resolve()
        for _ in range(10):
            candidate = current / "src" / "devrules" / "cli_commands"
            if candidate.exists() and candidate.is_dir():
                return candidate
            if current.parent == current:
                break
            current = current.parent
        return None

    cli_commands_dir = _find_cli_commands_dir(Path(__file__).parent)
    if cli_commands_dir is None:
        return False, "Could not locate src/devrules/cli_commands directory"

    python_files = sorted(
        p
        for p in cli_commands_dir.rglob("*.py")
        if p.is_file() and p.name != "__init__.py" and "prompters" not in p.parts
    )
    if not python_files:
        return False, f"No python modules found under {cli_commands_dir}"

    offenders: list[tuple[str, list[str]]] = []
    compliant = 0

    class _BodyUsageDetector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.typer_calls: set[str] = set()
            self.gum_calls: set[str] = set()

        def visit_Call(self, node: ast.Call) -> None:
            # Detect typer.method() calls
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                attr_name = node.func.attr

                if module_name == "typer":
                    self.typer_calls.add(attr_name)
                elif module_name == "gum":
                    self.gum_calls.add(attr_name)

            # Also detect typer.Exit() in calls (not just raises)
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "typer":
                    if node.func.attr == "Exit":
                        self.typer_calls.add("Exit")

            self.generic_visit(node)

        def visit_Raise(self, node: ast.Raise) -> None:
            # Catch `raise typer.Exit(...)`
            if node.exc:
                exc = node.exc
                if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Attribute):
                    if isinstance(exc.func.value, ast.Name) and exc.func.value.id == "typer":
                        if exc.func.attr == "Exit":
                            self.typer_calls.add("Exit")
            self.generic_visit(node)

    def _find_disallowed_in_function_bodies(module_ast: ast.Module) -> set[str]:
        detector = _BodyUsageDetector()

        for node in ast.walk(module_ast):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for stmt in node.body:
                    detector.visit(stmt)

        disallowed: set[str] = set()

        # Typer: flag common UI/output + Exit usage
        disallowed_typer = {
            "echo",
            "secho",
            "prompt",
            "confirm",
            "progressbar",
            "style",
            "colors",
            "Exit",
        }
        if detector.typer_calls & disallowed_typer:
            disallowed.add("typer")

        # Gum: any runtime call is considered disallowed
        if detector.gum_calls:
            disallowed.add("gum")

        return disallowed

    for path in python_files:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            offenders.append((str(path.relative_to(cli_commands_dir)), [f"unreadable file: {e}"]))
            continue

        reasons: list[str] = []

        try:
            module_ast = ast.parse(content)
        except SyntaxError as e:
            offenders.append((str(path.relative_to(cli_commands_dir)), [f"syntax error: {e}"]))
            continue

        found = _find_disallowed_in_function_bodies(module_ast)
        if "typer" in found:
            reasons.append("uses typer runtime calls in function body")
        if "gum" in found:
            reasons.append("uses gum runtime calls in function body")

        if reasons:
            offenders.append((str(path.relative_to(cli_commands_dir)), reasons))
        else:
            compliant += 1

    total = len(python_files)
    percent = round((compliant / total) * 100.0, 2) if total else 0.0

    if offenders:
        offenders_lines = "\n".join(
            f"  - {module} ({', '.join(reasons)})" for module, reasons in offenders
        )
        return (
            False,
            "\n".join(
                [
                    f"CLI commands prompter compliance: {percent}% ({compliant}/{total})",
                    "Non-compliant modules:",
                    offenders_lines,
                ]
            ),
        )

    return True, f"CLI commands prompter compliance: {percent}% ({compliant}/{total})"

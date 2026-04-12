import ast
from pathlib import Path

from devrules.core.enum import DevRulesEvent
from devrules.core.rules_engine import rule

# ============================================================
# AST helpers
# ============================================================


class _BodyUsageDetector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.typer_calls: set[str] = set()
        self.gum_calls: set[str] = set()
        self.header_calls: int = 0

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            module = node.func.value.id
            attr = node.func.attr

            if module == "typer":
                self.typer_calls.add(attr)
            elif module == "gum":
                self.gum_calls.add(attr)
            elif module == "prompter" and attr == "header":
                self.header_calls += 1

        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        if (
            node.exc
            and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Attribute)
            and isinstance(node.exc.func.value, ast.Name)
            and node.exc.func.value.id == "typer"
            and node.exc.func.attr == "Exit"
        ):
            self.typer_calls.add("Exit")

        self.generic_visit(node)


# ============================================================
# Module structure helpers
# ============================================================


def _find_register_function(module_ast: ast.Module) -> ast.FunctionDef | None:
    for node in module_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name == "register":
            return node
    return None


def _get_registered_commands(register_fn: ast.FunctionDef) -> list[ast.FunctionDef]:
    commands: list[ast.FunctionDef] = []

    for node in register_fn.body:
        if not isinstance(node, ast.FunctionDef):
            continue

        # Skip Typer callbacks (bootstrap functions)
        if _is_typer_callback(node):
            continue

        commands.append(node)

    return commands


def _is_typer_callback(fn: ast.FunctionDef) -> bool:
    for deco in fn.decorator_list:
        if (
            isinstance(deco, ast.Call)
            and isinstance(deco.func, ast.Attribute)
            and deco.func.attr == "callback"
        ):
            return True
    return False


# ============================================================
# Filesystem helpers
# ============================================================


def _find_cli_commands_dir(start: Path) -> Path | None:
    current = start.resolve()
    for _ in range(10):
        candidate = current / "src" / "devrules" / "cli_commands"
        if candidate.is_dir():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def _get_python_files(folder: Path) -> list[Path]:
    return sorted(
        p
        for p in folder.rglob("*.py")
        if p.is_file() and p.name != "__init__.py" and "prompters" not in p.parts
    )


# ============================================================
# Validation logic
# ============================================================


def _find_disallowed_in_registered_commands(module_ast: ast.Module) -> set[str]:
    register_fn = _find_register_function(module_ast)
    if not register_fn:
        return set()

    detector = _BodyUsageDetector()

    for command in _get_registered_commands(register_fn):
        detector.visit(command)

    disallowed: set[str] = set()

    if detector.typer_calls & {
        "echo",
        "secho",
        "prompt",
        "confirm",
        "progressbar",
        "style",
        "colors",
        "Exit",
    }:
        disallowed.add("typer")

    if detector.gum_calls:
        disallowed.add("gum")

    return disallowed


def _each_registered_command_has_header(module_ast: ast.Module) -> bool:
    register_fn = _find_register_function(module_ast)
    if not register_fn:
        return True

    for command in _get_registered_commands(register_fn):
        detector = _BodyUsageDetector()
        detector.visit(command)

        if detector.header_calls == 0:
            return False

    return True


# ============================================================
# Rules
# ============================================================


@rule(
    name="prompter_cli_validator",
    description="Validates cli commands use default prompter instead of typer or gum",
    hooks=[DevRulesEvent.PRE_COMMIT],
)
def valid_usage_of_auto_detected_prompter() -> tuple[bool, str]:
    cli_commands_dir = _find_cli_commands_dir(Path(__file__).parent)
    if cli_commands_dir is None:
        return False, "Could not locate src/devrules/cli_commands directory"

    python_files = _get_python_files(cli_commands_dir)
    if not python_files:
        return False, f"No python modules found under {cli_commands_dir}"

    offenders: list[tuple[str, list[str]]] = []
    compliant = 0

    for path in python_files:
        rel_path = str(path.relative_to(cli_commands_dir))

        try:
            module_ast = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError) as e:
            offenders.append((rel_path, [f"parse error: {e}"]))
            continue

        reasons: list[str] = []
        found = _find_disallowed_in_registered_commands(module_ast)

        if "typer" in found:
            reasons.append("uses typer runtime calls in command body")
        if "gum" in found:
            reasons.append("uses gum runtime calls in command body")

        if reasons:
            offenders.append((rel_path, reasons))
        else:
            compliant += 1

    total = len(python_files)
    percent = round((compliant / total) * 100.0, 2)

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


@rule(
    name="prompter_header_usage_cli_validator",
    description="Validates each cli command uses a header",
)
def valid_usage_of_headers_in_commands() -> tuple[bool, str]:
    cli_commands_dir = _find_cli_commands_dir(Path(__file__).parent)
    if cli_commands_dir is None:
        return False, "Could not locate src/devrules/cli_commands directory"

    python_files = _get_python_files(cli_commands_dir)
    if not python_files:
        return False, f"No python modules found under {cli_commands_dir}"

    missing_modules: list[str] = []

    for path in python_files:
        rel_path = str(path.relative_to(cli_commands_dir))

        try:
            module_ast = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            missing_modules.append(rel_path)
            continue

        if not _each_registered_command_has_header(module_ast):
            missing_modules.append(rel_path)

    if missing_modules:
        return (
            False,
            "These modules miss a header:\n  - " + "\n  - ".join(missing_modules),
        )

    return True, "Each command has a header call"

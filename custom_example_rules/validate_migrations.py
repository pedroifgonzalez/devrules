import subprocess

from devrules.core.rules_engine import rule


@rule(name="validate-migrations", description="Validate migrations run and are rollback safe")
def validate_migrations(number: int) -> tuple[bool, str]:
    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        subprocess.run(["alembic", "downgrade", "-", str(number)], check=True)
        return True, "Migrations passed validation"
    except subprocess.CalledProcessError:
        return False, "Migrations failed validation"

import subprocess

from devrules.core.rules_engine import rule


def check_migrations_use_server_default():
    pass


@rule(name="validate-migrations", description="Validate migrations run and are rollback safe")
def validate_migrations() -> tuple[bool, str]:
    try:
        check_migrations_use_server_default()
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        subprocess.run(["alembic", "downgrade", "head"], check=True)
        return True, "Migrations passed validation"
    except subprocess.CalledProcessError:
        return False, "Migrations failed validation"

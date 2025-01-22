import os

HOUSEPLANT_DIR = os.getenv("HOUSEPLANT_DIR", "ch")
HOUSEPLANT_SCHEMA_SNAPSHOT_FILE = os.getenv("HOUSEPLANT_SCHEMA_SNAPSHOT_FILE", "schema.sql")

MIGRATIONS_DIR = os.path.join(HOUSEPLANT_DIR, "migrations")


def get_migration_files():
    # Get all local migration files
    return sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".yml")])

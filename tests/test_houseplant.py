import os

import pytest

from houseplant.houseplant import Houseplant


@pytest.fixture
def houseplant():
    return Houseplant()


@pytest.fixture
def test_migration(tmp_path):
    # Set up test environment
    migrations_dir = tmp_path / "ch/migrations"
    migrations_dir.mkdir(parents=True)
    migration_file = migrations_dir / "20240101000000_test_migration.yml"

    migration_content = """version: "20240101000000"
name: test_migration
table: events

development: &development
  up: |
    CREATE TABLE {table} (
        id UInt32,
        name String
    ) ENGINE = MergeTree()
    ORDER BY id
  down: |
    DROP TABLE {table}

test:
  <<: *development

production:
  up: |
    CREATE TABLE {table} (
        id UInt32,
        name String
    ) ENGINE = ReplicatedMergeTree()
    ORDER BY id
  down: |
    DROP TABLE {table}
"""

    migration_file.write_text(migration_content)
    os.chdir(tmp_path)
    return migration_content


@pytest.fixture
def test_migration_with_table(tmp_path):
    # Set up test environment
    migrations_dir = tmp_path / "ch/migrations"
    migrations_dir.mkdir(parents=True)
    migration_file = migrations_dir / "20240101000000_test_settings.yml"

    migration_content = """version: "20240101000000"
name: test_settings
table: settings_table

table_definition: |
    id UInt32,
    name String,
    created_at DateTime
table_settings: |
    ORDER BY (id, created_at)
    PARTITION BY toYYYYMM(created_at)

development: &development
  up: |
    CREATE TABLE {table} (
        {table_definition}
    ) ENGINE = MergeTree()
    {table_settings}
  down: |
    DROP TABLE {table}

test:
  <<: *development

production:
  up: |
    CREATE TABLE {table} ON CLUSTER '{{cluster}}' (
        {table_definition}
    ) ENGINE = MergeTree()
    {table_settings}
  down: |
    DROP TABLE {table}
"""

    migration_file.write_text(migration_content)
    os.chdir(tmp_path)
    return migration_content


@pytest.fixture
def test_migration_with_view(tmp_path):
    # Set up test environment
    migrations_dir = tmp_path / "ch/migrations"
    migrations_dir.mkdir(parents=True)
    migration_file = migrations_dir / "20240101000000_test_view.yml"

    migration_content = """version: "20240101000000"
name: test_view
table: settings_table
sink_table: sink_table

view_definition: |
    id UInt32,
    name String,
    created_at DateTime
view_query: |
    SELECT * FROM events

development: &development
  up: |
    CREATE MATERIALIZED VIEW {table}
    TO {sink_table} (
      {view_definition}
    )
    AS {view_query}
  down: |
    DROP TABLE {table}

test:
  <<: *development

production:
  up: |
    CREATE MATERIALIZED VIEW {table}
    ON CLUSTER '{{cluster}}'
    TO {sink_table} (
      {view_definition}
    )
    AS {view_query}
  down: |
    DROP TABLE {table}
"""

    migration_file.write_text(migration_content)
    os.chdir(tmp_path)
    return migration_content


@pytest.fixture
def duplicate_migrations(tmp_path):
    # Set up test environment
    migrations_dir = tmp_path / "ch/migrations"
    migrations_dir.mkdir(parents=True)

    # Create two migrations that modify the same table
    migration1 = migrations_dir / "20240101000000_first_migration.yml"
    migration2 = migrations_dir / "20240102000000_second_migration.yml"

    migration1_content = """version: "{version}"
name: {name}
table: events

development: &development
  up: |
    CREATE TABLE events (
        id UInt32,
        name String
    ) ENGINE = MergeTree()
    ORDER BY id
  down: |
    DROP TABLE events

test:
  <<: *development

production:
  <<: *development
"""

    migration2_content = """version: "{version}"
name: {name}
table: events

development: &development
  up: |
    ALTER TABLE events ADD COLUMN description String
  down: |
    ALTER TABLE events DROP COLUMN description

test:
  <<: *development

production:
  <<: *development
"""

    migration1.write_text(
        migration1_content.format(version="20240101000000", name="first_migration")
    )
    migration2.write_text(
        migration2_content.format(version="20240102000000", name="second_migration")
    )

    os.chdir(tmp_path)
    return ("20240101000000", "20240102000000")


def test_migrate_up_development(houseplant, test_migration, mocker):
    # Mock environment and database calls
    houseplant.env = "development"
    mock_execute = mocker.patch.object(houseplant.db, "execute_migration")
    mock_mark_applied = mocker.patch.object(houseplant.db, "mark_migration_applied")
    mock_get_applied = mocker.patch.object(
        houseplant.db, "get_applied_migrations", return_value=[]
    )

    # Run migration
    houseplant.migrate_up()

    # Verify correct SQL was executed
    expected_sql = """CREATE TABLE events (
    id UInt32,
    name String
) ENGINE = MergeTree()
ORDER BY id"""
    mock_execute.assert_called_once_with(expected_sql)
    mock_mark_applied.assert_called_once_with("20240101000000")
    mock_get_applied.assert_called_once()


def test_migrate_up_production(houseplant, test_migration, mocker):
    # Mock environment and database calls
    houseplant.env = "production"
    mock_execute = mocker.patch.object(houseplant.db, "execute_migration")
    mock_mark_applied = mocker.patch.object(houseplant.db, "mark_migration_applied")
    mock_get_applied = mocker.patch.object(
        houseplant.db, "get_applied_migrations", return_value=[]
    )

    # Run migration
    houseplant.migrate_up()

    # Verify correct SQL was executed
    expected_sql = """CREATE TABLE events (
    id UInt32,
    name String
) ENGINE = ReplicatedMergeTree()
ORDER BY id"""
    mock_execute.assert_called_once_with(expected_sql)
    mock_mark_applied.assert_called_once_with("20240101000000")
    mock_get_applied.assert_called_once()


def test_migrate_up_with_development_table(
    houseplant, test_migration_with_table, mocker
):
    # Mock database calls
    houseplant.env = "development"
    mock_execute = mocker.patch.object(houseplant.db, "execute_migration")
    mock_mark_applied = mocker.patch.object(houseplant.db, "mark_migration_applied")
    mock_get_applied = mocker.patch.object(
        houseplant.db, "get_applied_migrations", return_value=[]
    )

    # Run migration
    houseplant.migrate_up()

    # Verify correct SQL was executed with table_definition and table_settings
    expected_sql = """CREATE TABLE settings_table (
    id UInt32,
name String,
created_at DateTime
) ENGINE = MergeTree()
ORDER BY (id, created_at)
PARTITION BY toYYYYMM(created_at)"""
    mock_execute.assert_called_once_with(expected_sql)
    mock_mark_applied.assert_called_once_with("20240101000000")
    mock_get_applied.assert_called_once()


def test_migrate_up_with_production_table(
    houseplant, test_migration_with_table, mocker
):
    # Mock database calls
    houseplant.env = "production"
    mock_execute = mocker.patch.object(houseplant.db, "execute_migration")
    mock_mark_applied = mocker.patch.object(houseplant.db, "mark_migration_applied")
    mock_get_applied = mocker.patch.object(
        houseplant.db, "get_applied_migrations", return_value=[]
    )

    # Run migration
    houseplant.migrate_up()

    # Verify correct SQL was executed with table_definition and table_settings
    expected_sql = """CREATE TABLE settings_table ON CLUSTER '{cluster}' (
    id UInt32,
name String,
created_at DateTime
) ENGINE = MergeTree()
ORDER BY (id, created_at)
PARTITION BY toYYYYMM(created_at)"""
    mock_execute.assert_called_once_with(expected_sql)
    mock_mark_applied.assert_called_once_with("20240101000000")
    mock_get_applied.assert_called_once()


def test_migrate_up_with_development_view(houseplant, test_migration_with_view, mocker):
    # Mock database calls
    houseplant.env = "development"
    mock_execute = mocker.patch.object(houseplant.db, "execute_migration")
    mock_mark_applied = mocker.patch.object(houseplant.db, "mark_migration_applied")
    mock_get_applied = mocker.patch.object(
        houseplant.db, "get_applied_migrations", return_value=[]
    )

    # Run migration
    houseplant.migrate_up()

    # Verify correct SQL was executed with view_definition and view_query
    expected_sql = """CREATE MATERIALIZED VIEW settings_table
TO sink_table (
  id UInt32,
name String,
created_at DateTime
)
AS SELECT * FROM events"""
    mock_execute.assert_called_once_with(expected_sql)
    mock_mark_applied.assert_called_once_with("20240101000000")
    mock_get_applied.assert_called_once()


def test_migrate_up_with_production_view(houseplant, test_migration_with_view, mocker):
    # Mock database calls
    houseplant.env = "production"
    mock_execute = mocker.patch.object(houseplant.db, "execute_migration")
    mock_mark_applied = mocker.patch.object(houseplant.db, "mark_migration_applied")
    mock_get_applied = mocker.patch.object(
        houseplant.db, "get_applied_migrations", return_value=[]
    )

    # Run migration
    houseplant.migrate_up()

    # Verify correct SQL was executed with view_definition and view_query
    expected_sql = """CREATE MATERIALIZED VIEW settings_table
ON CLUSTER '{cluster}'
TO sink_table (
  id UInt32,
name String,
created_at DateTime
)
AS SELECT * FROM events"""
    mock_execute.assert_called_once_with(expected_sql)
    mock_mark_applied.assert_called_once_with("20240101000000")
    mock_get_applied.assert_called_once()


def test_update_schema_no_duplicates(houseplant, duplicate_migrations, mocker):
    versions = duplicate_migrations

    # Mock database calls
    mocker.patch.object(
        houseplant.db,
        "get_applied_migrations",
        return_value=[(versions[0],), (versions[1],)],
    )
    mocker.patch.object(
        houseplant.db, "get_database_tables", return_value=[("events",)]
    )
    mocker.patch.object(
        houseplant.db, "get_database_materialized_views", return_value=[]
    )
    mocker.patch.object(houseplant.db, "get_database_dictionaries", return_value=[])

    # Mock the SHOW CREATE TABLE call
    mocker.patch.object(
        houseplant.db.client,
        "execute",
        return_value=[
            [
                "CREATE TABLE events (id UInt32, name String) ENGINE = MergeTree() ORDER BY id"
            ]
        ],
    )

    # Update schema
    houseplant.update_schema()

    # Read the generated schema file
    with open("ch/schema.sql", "r") as f:
        schema_content = f.read()

    # Verify the table appears only once in the schema
    table_count = schema_content.count("CREATE TABLE events")
    assert (
        table_count == 1
    ), f"Table 'events' appears {table_count} times in schema, expected 1"


def test_db_schema_load(houseplant, test_migration, mocker):
    # Mock database calls
    mock_mark_applied = mocker.patch.object(houseplant.db, "mark_migration_applied")

    # Run schema load
    houseplant.db_schema_load()

    # Verify migration was marked as applied without executing SQL
    mock_mark_applied.assert_called_once_with("20240101000000")


@pytest.mark.skip
def test_migrate_down(houseplant, test_migration, mocker):
    # Mock database calls
    mock_execute = mocker.patch.object(houseplant.db, "execute_migration")
    mock_mark_rolled_back = mocker.patch.object(
        houseplant.db, "mark_migration_rolled_back"
    )
    mock_get_applied = mocker.patch.object(
        houseplant.db, "get_applied_migrations", return_value=[("20240101000000",)]
    )

    # Roll back migration
    houseplant.migrate_down()

    # Verify correct SQL was executed
    mock_execute.assert_called_once_with("DROP TABLE events")
    mock_mark_rolled_back.assert_called_once_with("20240101000000")
    mock_get_applied.assert_called_once()

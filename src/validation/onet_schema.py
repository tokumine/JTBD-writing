"""O*NET database schema validation."""
import logging
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of schema validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    table_info: dict[str, list[str]] = field(default_factory=dict)


class ONetSchemaValidator:
    """Validate O*NET database schema before any queries."""

    REQUIRED_TABLES: dict[str, list[str]] = {
        "task_statements": ["task_id", "onetsoc_code", "task"],
        "occupation_data": ["onetsoc_code", "title"],
        "job_zones": ["onetsoc_code", "job_zone"],
    }

    # Optional tables that enhance functionality
    OPTIONAL_TABLES: dict[str, list[str]] = {
        "work_context": ["onetsoc_code", "element_id", "scale_id", "data_value"],
        "skills": ["onetsoc_code", "element_id", "scale_id", "data_value"],
        "content_model_reference": ["element_id", "element_name"],
    }

    # Element IDs for writing-related skills
    WRITING_ELEMENTS = {
        "2.A.1.c": "Writing",
        "4.C.1.a.2.h": "Electronic Mail",
        "4.C.1.a.2.j": "Letters and Memos",
    }

    REQUIRED_SCALES = ["IM", "LV", "CX"]

    async def validate(self, db_path: Path) -> ValidationResult:
        """Run comprehensive schema validation."""
        errors: list[str] = []
        warnings: list[str] = []
        table_info: dict[str, list[str]] = {}

        if not db_path.exists():
            return ValidationResult(
                is_valid=False,
                errors=[f"Database not found: {db_path}"],
                warnings=[],
                table_info={},
            )

        try:
            async with aiosqlite.connect(db_path) as db:
                # Get all tables
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                existing_tables = {row[0] for row in await cursor.fetchall()}

                # Validate required tables and columns
                for table, required_cols in self.REQUIRED_TABLES.items():
                    if table not in existing_tables:
                        errors.append(f"Missing required table: {table}")
                        continue

                    # Get actual columns (case-insensitive check)
                    cursor = await db.execute(f"PRAGMA table_info({table})")
                    actual_cols = {
                        row[1].lower(): row[1] for row in await cursor.fetchall()
                    }
                    table_info[table] = list(actual_cols.values())

                    for col in required_cols:
                        if col.lower() not in actual_cols:
                            errors.append(f"Missing column: {table}.{col}")

                # Check optional tables
                for table, required_cols in self.OPTIONAL_TABLES.items():
                    if table not in existing_tables:
                        warnings.append(f"Optional table missing: {table}")
                        continue

                    cursor = await db.execute(f"PRAGMA table_info({table})")
                    actual_cols = {
                        row[1].lower(): row[1] for row in await cursor.fetchall()
                    }
                    table_info[table] = list(actual_cols.values())

                    for col in required_cols:
                        if col.lower() not in actual_cols:
                            warnings.append(f"Missing column in optional table: {table}.{col}")

                # Validate data presence in required tables
                for table in self.REQUIRED_TABLES:
                    if table in existing_tables:
                        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                        count = (await cursor.fetchone())[0]
                        if count == 0:
                            errors.append(f"Table {table} is empty")

        except Exception as e:
            errors.append(f"Database access error: {e}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            table_info=table_info,
        )

    async def get_table_stats(self, db_path: Path) -> dict[str, int]:
        """Get row counts for all tables."""
        stats: dict[str, int] = {}

        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in await cursor.fetchall()]

            for table in tables:
                cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = (await cursor.fetchone())[0]

        return stats

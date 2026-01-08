"""Extract writing-relevant tasks from O*NET database."""
import re
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from src.prompts.schemas import ONetTask


class ONetExtractor:
    """Extract writing-relevant tasks with memory-efficient streaming."""

    # Pre-compiled regex patterns for writing detection
    WRITING_PATTERNS: list[tuple[re.Pattern[str], float]] = [
        (re.compile(r"\bwrite\b", re.I), 1.0),
        (re.compile(r"\bdraft\b", re.I), 1.0),
        (re.compile(r"\bcompose\b", re.I), 1.0),
        (re.compile(r"\bdocument\b", re.I), 0.8),
        (re.compile(r"\breport\b", re.I), 0.7),
        (re.compile(r"\bcorrespond", re.I), 0.9),
        (re.compile(r"\bemail\b", re.I), 0.9),
        (re.compile(r"\bmemo\b", re.I), 0.9),
        (re.compile(r"\bletter\b", re.I), 0.8),
        (re.compile(r"\bcommunicat", re.I), 0.6),
        (re.compile(r"\bpresent\b", re.I), 0.5),
        (re.compile(r"\bsummariz", re.I), 0.7),
        (re.compile(r"\bpropos", re.I), 0.7),
        (re.compile(r"\bnotify\b", re.I), 0.8),
        (re.compile(r"\binform\b", re.I), 0.7),
    ]

    def __init__(self, db_path: Path):
        """Initialize extractor with database path."""
        self.db_path = db_path

    async def extract_writing_tasks(
        self,
        min_relevance: float = 0.5,
        job_zones: list[int] | None = None,
        soc_codes: list[str] | None = None,
        limit: int | None = None,
    ) -> list[ONetTask]:
        """Extract tasks with writing relevance above threshold."""
        tasks = []
        count = 0
        async for task in self._stream_tasks(min_relevance, job_zones, soc_codes):
            tasks.append(task)
            count += 1
            if limit and count >= limit:
                break
        return tasks

    async def _stream_tasks(
        self,
        min_relevance: float,
        job_zones: list[int] | None,
        soc_codes: list[str] | None,
    ) -> AsyncIterator[ONetTask]:
        """Stream tasks one at a time to avoid memory explosion."""
        query = """
        SELECT
            t.task_id,
            t.onetsoc_code,
            t.task,
            COALESCE(t.task_type, 'Core') as task_type,
            o.title as occupation_title,
            o.description as occupation_description,
            COALESCE(jz.job_zone, 3) as job_zone,
            SUBSTR(t.onetsoc_code, 1, 2) as soc_major
        FROM task_statements t
        JOIN occupation_data o ON t.onetsoc_code = o.onetsoc_code
        LEFT JOIN job_zones jz ON t.onetsoc_code = jz.onetsoc_code
        """

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                async for row in cursor:
                    row_dict = dict(row)

                    # Apply filters early
                    if job_zones and row_dict["job_zone"] not in job_zones:
                        continue
                    if soc_codes and row_dict["soc_major"] not in soc_codes:
                        continue

                    # Compute relevance
                    relevance = self._compute_writing_relevance(row_dict)
                    if relevance < min_relevance:
                        continue

                    yield ONetTask(
                        task_id=str(row_dict["task_id"]),
                        onetsoc_code=row_dict["onetsoc_code"],
                        task=row_dict["task"],
                        task_type=row_dict["task_type"],
                        occupation_title=row_dict["occupation_title"],
                        occupation_description=row_dict.get("occupation_description"),
                        job_zone=row_dict["job_zone"],
                        soc_major_group=row_dict["soc_major"],
                        writing_relevance_score=relevance,
                        inferred_category=self._infer_category(row_dict["task"]),
                        inferred_channel=self._infer_channel(row_dict["task"]),
                    )

    def _compute_writing_relevance(self, row: dict) -> float:
        """Compute writing relevance with proper normalization."""
        task_text = row.get("task", "")

        # Pattern matching score
        max_pattern_score = 0.0
        for pattern, weight in self.WRITING_PATTERNS:
            if pattern.search(task_text):
                max_pattern_score = max(max_pattern_score, weight)

        return max_pattern_score

    def _infer_category(self, task_text: str) -> str:
        """Multi-signal category inference."""
        task_lower = task_text.lower()
        scores: dict[str, float] = {}

        patterns = [
            ("customer_communication", ["customer", "client", "patient", "stakeholder"], 1.5),
            ("correspondence", ["email", "correspond", "letter", "reply"], 1.3),
            ("documentation", ["document", "record", "log", "file"], 1.2),
            ("reports", ["report", "summary", "analysis", "findings"], 1.1),
            ("proposals", ["propos", "recommend", "suggest", "request"], 1.1),
            ("training", ["train", "instruct", "teach", "guide"], 1.0),
            ("policy", ["policy", "procedure", "guideline", "standard"], 1.0),
            ("evaluation", ["review", "evaluat", "assess", "feedback"], 1.0),
        ]

        for category, keywords, weight in patterns:
            score = sum(weight for kw in keywords if kw in task_lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return "general_communication"
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def _infer_channel(self, task_text: str) -> str:
        """Infer communication channel."""
        task_lower = task_text.lower()

        channel_patterns = [
            ("email", ["email", "e-mail"]),
            ("letter", ["letter"]),
            ("memo", ["memo", "memorandum"]),
            ("report", ["report"]),
            ("social_media", ["post", "social", "blog", "tweet"]),
            ("presentation", ["present", "slide"]),
        ]

        for channel, keywords in channel_patterns:
            if any(kw in task_lower for kw in keywords):
                return channel

        return "unspecified"

    async def get_occupation_count(self) -> int:
        """Get count of unique occupations with tasks."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(DISTINCT onetsoc_code) FROM task_statements"
            )
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_task_count(self) -> int:
        """Get total count of tasks."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM task_statements")
            result = await cursor.fetchone()
            return result[0] if result else 0

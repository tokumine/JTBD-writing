"""SQLite database operations for evaluation results."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from src.eval.schemas import AggregatedResult, EvalState, ModelResponse


class EvalDatabase:
    """Async SQLite database for evaluation storage."""

    SCHEMA = """
    -- Evaluation runs
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        preset_name TEXT,
        config_json TEXT,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        status TEXT DEFAULT 'running',
        total_prompts INTEGER,
        completed_prompts INTEGER DEFAULT 0,
        total_cost_usd REAL DEFAULT 0.0
    );

    -- Generated prompts
    CREATE TABLE IF NOT EXISTS prompts (
        prompt_id TEXT PRIMARY KEY,
        run_id TEXT,
        prompt_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    );

    -- Model responses
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id TEXT,
        model_id TEXT,
        response_text TEXT,
        status TEXT,
        latency_ms REAL,
        input_tokens INTEGER,
        output_tokens INTEGER,
        word_count INTEGER,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    -- Judgments
    CREATE TABLE IF NOT EXISTS judgments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id TEXT,
        model_a TEXT,
        model_b TEXT,
        judge_model TEXT,
        persona_type TEXT,
        position_order TEXT,
        winner TEXT,
        confidence TEXT,
        reasoning TEXT,
        scores_json TEXT,
        weaknesses_a_json TEXT,
        weaknesses_b_json TEXT,
        raw_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    -- Aggregated results
    CREATE TABLE IF NOT EXISTS results (
        prompt_id TEXT,
        model_a TEXT,
        model_b TEXT,
        winner TEXT,
        votes_model_a INTEGER,
        votes_model_b INTEGER,
        votes_tie INTEGER,
        inter_judge_agreement REAL,
        position_consistency REAL,
        margin REAL,
        confidence TEXT,
        gemini_model_id TEXT,
        gemini_was_a INTEGER,
        PRIMARY KEY (prompt_id, model_a, model_b),
        FOREIGN KEY (prompt_id) REFERENCES prompts(prompt_id)
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_responses_prompt ON responses(prompt_id);
    CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);
    CREATE INDEX IF NOT EXISTS idx_judgments_prompt ON judgments(prompt_id);
    CREATE INDEX IF NOT EXISTS idx_results_winner ON results(winner);
    """

    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to database and initialize schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.executescript(self.SCHEMA)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> "EvalDatabase":
        """Enter async context."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context."""
        await self.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the connection, raising if not connected."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    # Run management
    async def create_run(
        self,
        run_id: str,
        preset_name: str,
        config: dict[str, Any],
        total_prompts: int,
    ) -> None:
        """Create a new evaluation run."""
        await self.connection.execute(
            """
            INSERT INTO runs (run_id, preset_name, config_json, started_at, total_prompts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, preset_name, json.dumps(config), datetime.now(), total_prompts),
        )
        await self.connection.commit()

    async def update_run_progress(
        self,
        run_id: str,
        completed_prompts: int,
        total_cost_usd: float,
    ) -> None:
        """Update run progress."""
        await self.connection.execute(
            """
            UPDATE runs
            SET completed_prompts = ?, total_cost_usd = ?
            WHERE run_id = ?
            """,
            (completed_prompts, total_cost_usd, run_id),
        )
        await self.connection.commit()

    async def complete_run(self, run_id: str) -> None:
        """Mark run as complete."""
        await self.connection.execute(
            """
            UPDATE runs
            SET status = 'complete', completed_at = ?
            WHERE run_id = ?
            """,
            (datetime.now(), run_id),
        )
        await self.connection.commit()

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get run by ID."""
        cursor = await self.connection.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        columns = [d[0] for d in cursor.description]
        return dict(zip(columns, row))

    # Prompt storage
    async def save_prompt(
        self,
        prompt_id: str,
        run_id: str,
        prompt_data: dict[str, Any],
    ) -> None:
        """Save a generated prompt."""
        await self.connection.execute(
            """
            INSERT OR REPLACE INTO prompts (prompt_id, run_id, prompt_json)
            VALUES (?, ?, ?)
            """,
            (prompt_id, run_id, json.dumps(prompt_data)),
        )
        await self.connection.commit()

    # Response storage
    async def save_response(self, response: ModelResponse) -> None:
        """Save a model response."""
        await self.connection.execute(
            """
            INSERT INTO responses
            (prompt_id, model_id, response_text, status, latency_ms,
             input_tokens, output_tokens, word_count, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                response.prompt_id,
                response.model_id,
                response.response_text,
                response.status,
                response.latency_ms,
                response.input_tokens,
                response.output_tokens,
                response.word_count,
                response.error,
            ),
        )
        await self.connection.commit()

    async def get_responses(self, prompt_id: str) -> list[dict[str, Any]]:
        """Get all responses for a prompt."""
        cursor = await self.connection.execute(
            "SELECT * FROM responses WHERE prompt_id = ?",
            (prompt_id,),
        )
        rows = await cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    # Result storage
    async def save_result(self, result: AggregatedResult) -> None:
        """Save an aggregated result."""
        await self.connection.execute(
            """
            INSERT OR REPLACE INTO results
            (prompt_id, model_a, model_b, winner, votes_model_a, votes_model_b,
             votes_tie, inter_judge_agreement, position_consistency, margin,
             confidence, gemini_model_id, gemini_was_a)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.prompt_id,
                result.model_a,
                result.model_b,
                result.winner,
                result.votes_model_a,
                result.votes_model_b,
                result.votes_tie,
                result.inter_judge_agreement,
                result.position_consistency,
                result.margin,
                result.confidence,
                result.gemini_model_id,
                1 if result.gemini_was_a else 0,
            ),
        )
        await self.connection.commit()

    async def get_win_rates(self, run_id: str | None = None) -> dict[str, dict[str, float]]:
        """Get win rates by model pair."""
        query = """
            SELECT model_a, model_b,
                   SUM(CASE WHEN winner = model_a THEN 1 ELSE 0 END) as a_wins,
                   SUM(CASE WHEN winner = model_b THEN 1 ELSE 0 END) as b_wins,
                   SUM(CASE WHEN winner = 'TIE' THEN 1 ELSE 0 END) as ties,
                   COUNT(*) as total
            FROM results r
        """
        if run_id:
            query += " JOIN prompts p ON r.prompt_id = p.prompt_id WHERE p.run_id = ?"
            params: tuple = (run_id,)
        else:
            params = ()

        query += " GROUP BY model_a, model_b"

        cursor = await self.connection.execute(query, params)
        rows = await cursor.fetchall()

        win_rates: dict[str, dict[str, float]] = {}
        for row in rows:
            model_a, model_b, a_wins, b_wins, ties, total = row
            key = f"{model_a} vs {model_b}"
            if total > 0:
                win_rates[key] = {
                    "model_a_win_rate": a_wins / total,
                    "model_b_win_rate": b_wins / total,
                    "tie_rate": ties / total,
                    "total_comparisons": total,
                }

        return win_rates

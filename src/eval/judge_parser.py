"""Parse judge model responses."""
import json
import re
from typing import Any, Literal

from src.eval.schemas import JudgmentResult
from src.exceptions import ParseError


class JudgeParser:
    """Parse structured judgment from LLM output."""

    def parse(self, response_text: str) -> JudgmentResult:
        """
        Parse judgment from response text.

        Args:
            response_text: Raw response from judge model

        Returns:
            JudgmentResult with parsed data
        """
        try:
            data = self._extract_json(response_text)
            return self._validate_and_build(data, response_text)
        except Exception as e:
            # Return parse error result
            return JudgmentResult(
                winner="PARSE_ERROR",
                confidence="unknown",
                reasoning=f"Parse failed: {e}",
                parse_success=False,
                raw_response=response_text[:1000],
            )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract JSON object from text."""
        text = text.strip()

        # Try direct parse
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Try extracting from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in text
        obj_match = re.search(r"\{[\s\S]*\}", text)
        if obj_match:
            try:
                return json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ParseError("Could not extract JSON from response", raw_output=text[:500])

    def _validate_and_build(
        self,
        data: dict[str, Any],
        raw_response: str,
    ) -> JudgmentResult:
        """Validate parsed data and build result."""
        # Extract winner
        winner_raw = data.get("winner", "").upper().strip()
        if winner_raw in ["A", "B", "TIE"]:
            winner: Literal["A", "B", "TIE", "PARSE_ERROR"] = winner_raw  # type: ignore
        else:
            winner = "PARSE_ERROR"

        # Extract confidence
        confidence_raw = data.get("confidence", "").lower().strip()
        if confidence_raw in ["high", "medium", "low"]:
            confidence: Literal["high", "medium", "low", "unknown"] = confidence_raw  # type: ignore
        else:
            confidence = "unknown"

        # Extract optional fields
        scores = data.get("scores")
        if scores and not isinstance(scores, dict):
            scores = None

        weaknesses_a = data.get("weaknesses_a", [])
        if not isinstance(weaknesses_a, list):
            weaknesses_a = []

        weaknesses_b = data.get("weaknesses_b", [])
        if not isinstance(weaknesses_b, list):
            weaknesses_b = []

        return JudgmentResult(
            winner=winner,
            confidence=confidence,
            reasoning=str(data.get("reasoning", "")),
            scores=scores,
            weaknesses_a=weaknesses_a,
            weaknesses_b=weaknesses_b,
            parse_success=winner != "PARSE_ERROR",
            raw_response=raw_response[:1000] if winner == "PARSE_ERROR" else None,
        )

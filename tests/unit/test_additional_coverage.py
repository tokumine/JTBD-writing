"""Additional tests to boost coverage."""
import pytest

from src.data.company_database import CompanyDatabase
from src.data.naics_mapper import NAICSMapper
from src.data.name_generator import NameGenerator
from src.eval.judge_parser import JudgeParser


class TestCompanyDatabaseCoverage:
    """Additional coverage for company database."""

    def test_get_companies_by_sector(self) -> None:
        """Test getting companies by sector."""
        db = CompanyDatabase()
        companies = db.get_companies_by_sector("52")  # Finance

        # Should have at least one finance company
        assert len(companies) >= 1
        for c in companies:
            assert c.naics_sector == "52"


class TestNAICSMapperCoverage:
    """Additional coverage for NAICS mapper."""

    def test_get_sector_name(self) -> None:
        """Test getting sector name."""
        mapper = NAICSMapper()
        name = mapper.get_sector_name("54")

        assert name == "Professional, Scientific, and Technical Services"

    def test_get_sector_name_unknown(self) -> None:
        """Test getting unknown sector name."""
        mapper = NAICSMapper()
        name = mapper.get_sector_name("99")

        assert name == "Unknown"


class TestNameGeneratorCoverage:
    """Additional coverage for name generator."""

    def test_batch_without_diversity(self) -> None:
        """Test batch generation without diversity enforcement."""
        generator = NameGenerator()
        names = generator.generate_batch(count=5, seed=42, ensure_diversity=False)

        assert len(names) == 5


class TestJudgeParserCoverage:
    """Additional coverage for judge parser."""

    def test_parse_with_only_winner(self) -> None:
        """Test parsing response with only winner."""
        parser = JudgeParser()
        response = '{"winner": "A"}'

        result = parser.parse(response)

        assert result.winner == "A"
        assert result.confidence == "unknown"

    def test_parse_invalid_confidence(self) -> None:
        """Test parsing with invalid confidence."""
        parser = JudgeParser()
        response = '{"winner": "B", "confidence": "very high"}'

        result = parser.parse(response)

        assert result.winner == "B"
        assert result.confidence == "unknown"

    def test_parse_invalid_weaknesses(self) -> None:
        """Test parsing with invalid weaknesses format."""
        parser = JudgeParser()
        response = '{"winner": "A", "weaknesses_a": "not a list", "weaknesses_b": 123}'

        result = parser.parse(response)

        assert result.winner == "A"
        assert result.weaknesses_a == []
        assert result.weaknesses_b == []

    def test_parse_invalid_scores(self) -> None:
        """Test parsing with invalid scores format."""
        parser = JudgeParser()
        response = '{"winner": "A", "scores": "not a dict"}'

        result = parser.parse(response)

        assert result.winner == "A"
        assert result.scores is None

"""Report generation for evaluation results."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

# Try to import weasyprint, but don't fail if system deps are missing
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except OSError:
    WEASYPRINT_AVAILABLE = False

# HTML template for the report
REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Evaluation Report - {{ run_id }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 40px;
            color: #333;
            line-height: 1.6;
        }
        h1 {
            color: #1a1a1a;
            border-bottom: 3px solid #4A90D9;
            padding-bottom: 10px;
        }
        h2 {
            color: #2c3e50;
            margin-top: 30px;
        }
        .summary-box {
            background: #f8f9fa;
            border-left: 4px solid #4A90D9;
            padding: 15px 20px;
            margin: 20px 0;
        }
        .summary-box p {
            margin: 5px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #4A90D9;
            color: white;
        }
        tr:hover {
            background: #f5f5f5;
        }
        .win-rate {
            font-weight: bold;
            font-size: 1.2em;
        }
        .winner {
            color: #27ae60;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 0.9em;
        }
        .metric {
            display: inline-block;
            margin-right: 30px;
        }
        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #4A90D9;
        }
        .metric-label {
            font-size: 0.85em;
            color: #666;
        }
    </style>
</head>
<body>
    <h1>Gemini Writing Evaluation Report</h1>

    <div class="summary-box">
        <p><strong>Run ID:</strong> {{ run_id }}</p>
        <p><strong>Generated:</strong> {{ generated_at }}</p>
        <p><strong>Preset:</strong> {{ preset }}</p>
        <p><strong>Total Prompts:</strong> {{ total_prompts }}</p>
        <p><strong>Total Cost:</strong> ${{ "%.2f"|format(total_cost) }}</p>
    </div>

    <h2>Summary Metrics</h2>
    <div>
        {% for model, stats in rankings %}
        <div class="metric">
            <div class="metric-value">{{ "%.1f"|format(stats.win_rate * 100) }}%</div>
            <div class="metric-label">{{ model }} win rate</div>
        </div>
        {% endfor %}
    </div>

    <h2>Overall Rankings</h2>
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Model</th>
                <th>Win Rate</th>
                <th>Wins</th>
                <th>Total Comparisons</th>
            </tr>
        </thead>
        <tbody>
            {% for model, stats in rankings %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ model }}</td>
                <td class="win-rate {% if loop.index == 1 %}winner{% endif %}">
                    {{ "%.1f"|format(stats.win_rate * 100) }}%
                </td>
                <td>{{ stats.wins }}</td>
                <td>{{ stats.total }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    {% if model_pairs %}
    <h2>Head-to-Head Results</h2>
    <table>
        <thead>
            <tr>
                <th>Comparison</th>
                <th>Model A Wins</th>
                <th>Model B Wins</th>
                <th>Ties</th>
            </tr>
        </thead>
        <tbody>
            {% for pair_name, pair_stats in model_pairs.items() %}
            <tr>
                <td>{{ pair_name.replace('_', ' ') }}</td>
                <td>{{ pair_stats.values() | list | first if pair_stats else 'N/A' }}</td>
                <td>{{ pair_stats.values() | list | batch(2) | first | last if pair_stats else 'N/A' }}</td>
                <td>{{ pair_stats.get('ties', 0) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}

    <h2>Methodology</h2>
    <p>
        This evaluation compared LLM writing capabilities using professional writing tasks
        from the O*NET database. Each model's response was evaluated by judge models using
        pairwise comparisons.
    </p>
    <ul>
        <li><strong>Task Source:</strong> O*NET professional writing tasks</li>
        <li><strong>Evaluation Method:</strong> Pairwise comparison by LLM judges</li>
        <li><strong>Position Bias Control:</strong> {{ "Yes (position shuffling)" if position_shuffle else "No" }}</li>
        <li><strong>Votes per Judge:</strong> {{ votes_per_judge }}</li>
    </ul>

    <div class="footer">
        <p>Generated by Gemini Writing Evaluation Framework</p>
        <p>{{ generated_at }}</p>
    </div>
</body>
</html>
"""


class PDFReportGenerator:
    """Generate PDF reports from evaluation results."""

    def __init__(self, run_dir: Path):
        """Initialize with run directory."""
        self.run_dir = run_dir
        self.template = Template(REPORT_TEMPLATE)

    def generate(self, output_path: Path | None = None, format: str = "auto") -> Path:
        """Generate report (PDF if available, otherwise HTML)."""
        # Load results
        results = self._load_results()

        # Render HTML
        html_content = self.template.render(**results)

        # Determine format
        if format == "auto":
            format = "pdf" if WEASYPRINT_AVAILABLE else "html"

        if format == "pdf":
            if not WEASYPRINT_AVAILABLE:
                raise RuntimeError(
                    "PDF generation requires system libraries. "
                    "Install with: brew install cairo pango gdk-pixbuf libffi\n"
                    "Or use --format html for HTML report."
                )
            if output_path is None:
                output_path = self.run_dir / "report.pdf"
            HTML(string=html_content).write_pdf(output_path)
        else:
            if output_path is None:
                output_path = self.run_dir / "report.html"
            with open(output_path, "w") as f:
                f.write(html_content)

        return output_path

    def _load_results(self) -> dict[str, Any]:
        """Load results from run directory."""
        # Try to load checkpoint for metadata
        checkpoint_file = self.run_dir / "checkpoint.json"
        run_id = self.run_dir.name
        preset = "unknown"
        total_prompts = 0
        total_cost = 0.0

        if checkpoint_file.exists():
            with open(checkpoint_file) as f:
                checkpoint = json.load(f)
                run_id = checkpoint.get("run_id", run_id)
                total_prompts = checkpoint.get("total_prompts", 0)
                total_cost = checkpoint.get("total_cost_usd", 0.0)

        # Try to load results summary
        results_file = self.run_dir / "results.json"
        rankings = []
        model_pairs = {}

        if results_file.exists():
            with open(results_file) as f:
                results_data = json.load(f)
                if "overall_rankings" in results_data:
                    rankings = sorted(
                        results_data["overall_rankings"].items(),
                        key=lambda x: x[1].get("win_rate", 0),
                        reverse=True,
                    )
                model_pairs = results_data.get("model_pairs", {})

        # If no results file, try to compute from database
        if not rankings:
            rankings = self._compute_rankings_from_db()

        return {
            "run_id": run_id,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "preset": preset,
            "total_prompts": total_prompts,
            "total_cost": total_cost,
            "rankings": rankings,
            "model_pairs": model_pairs,
            "position_shuffle": True,
            "votes_per_judge": 1,
        }

    def _compute_rankings_from_db(self) -> list[tuple[str, dict[str, Any]]]:
        """Compute rankings from database if results.json doesn't exist."""
        db_path = self.run_dir / "eval.db"
        if not db_path.exists():
            return []

        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT model_a, model_b, winner,
                       COUNT(*) as count
                FROM results
                GROUP BY model_a, model_b, winner
            """)
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

        # Aggregate wins
        model_wins: dict[str, int] = {}
        model_total: dict[str, int] = {}

        for model_a, model_b, winner, count in rows:
            if winner == model_a:
                model_wins[model_a] = model_wins.get(model_a, 0) + count
            elif winner == model_b:
                model_wins[model_b] = model_wins.get(model_b, 0) + count

            model_total[model_a] = model_total.get(model_a, 0) + count
            model_total[model_b] = model_total.get(model_b, 0) + count

        rankings = []
        for model in set(model_wins.keys()) | set(model_total.keys()):
            wins = model_wins.get(model, 0)
            total = model_total.get(model, 0)
            win_rate = wins / total if total > 0 else 0
            rankings.append((model, {"wins": wins, "total": total, "win_rate": win_rate}))

        return sorted(rankings, key=lambda x: x[1]["win_rate"], reverse=True)


def generate_report(run_dir: Path, output_path: Path | None = None, format: str = "auto") -> Path:
    """Generate report for an evaluation run."""
    generator = PDFReportGenerator(run_dir)
    return generator.generate(output_path, format=format)

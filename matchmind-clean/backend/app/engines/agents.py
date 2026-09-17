class StatsAgent:
    def analyze(self, stats: dict) -> dict:
        """Analyzes expected goals (xG), shots, and possession performance."""
        home_xg = stats.get("home_xg", 1.3)
        away_xg = stats.get("away_xg", 1.1)
        score_trend = "Home attacking dominance" if home_xg > away_xg else "Away attacking edge"
        return {
            "agent": "Stats Agent",
            "focus": "xG, Shots on Target, Possession",
            "assessment": f"Home xG: {home_xg}, Away xG: {away_xg}. {score_trend}"
        }

class FormAgent:
    def analyze(self, form_data: dict) -> dict:
        """Analyzes recent 5/10 match trends, scoring and conceding patterns."""
        home_form = form_data.get("home_form", "W-W-D-L-W")
        away_form = form_data.get("away_form", "L-W-D-D-W")
        return {
            "agent": "Form Agent",
            "focus": "Last 5 matches, goals trend, home/away split",
            "assessment": f"Home Trend: {home_form} | Away Trend: {away_form}"
        }

class TacticalAgent:
    def analyze(self, tactical_data: dict) -> dict:
        """Analyzes tactical formations, pressing styles and head-to-head match-ups."""
        home_formation = tactical_data.get("home_formation", "4-3-3")
        away_formation = tactical_data.get("away_formation", "4-4-2")
        return {
            "agent": "Tactical Agent",
            "focus": "Formation, pressing intensity, tactical matchup",
            "assessment": f"Matchup: {home_formation} vs {away_formation}. Midfield press advantage expected."
        }

class ConsensusEngine:
    def __init__(self):
        self.stats_agent = StatsAgent()
        self.form_agent = FormAgent()
        self.tactical_agent = TacticalAgent()

    def evaluate(self, match_data: dict) -> dict:
        s_res = self.stats_agent.analyze(match_data)
        f_res = self.form_agent.analyze(match_data)
        t_res = self.tactical_agent.analyze(match_data)
        
        return {
            "consensus_summary": "Unified AI prediction generated from multi-agent analysis.",
            "agents_breakdown": [s_res, f_res, t_res]
        }

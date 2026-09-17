import math

def factorial(n: int) -> int:
    if n < 0:
        return 0
    return math.factorial(n)

def poisson_probability(lmbda: float, k: int) -> float:
    """Calculate Poisson probability P(X = k) = (lambda^k * e^-lambda) / k!"""
    if lmbda <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.pow(lmbda, k) * math.exp(-lmbda)) / factorial(k)

def calculate_match_probabilities(home_xg: float, away_xg: float, max_goals: int = 6):
    """
    Calculate exact 1X2, Over/Under 2.5, and BTTS probabilities 
    using the Poisson distribution model based on team xG.
    """
    home_win = 0.0
    draw = 0.0
    away_win = 0.0
    over_25 = 0.0
    btts = 0.0

    for h in range(max_goals + 1):
        p_home = poisson_probability(home_xg, h)
        for a in range(max_goals + 1):
            p_away = poisson_probability(away_xg, a)
            
            p_score = p_home * p_away

            if h > a:
                home_win += p_score
            elif h == a:
                draw += p_score
            else:
                away_win += p_score

            if h + a > 2.5:
                over_25 += p_score
            
            if h > 0 and a > 0:
                btts += p_score

    return {
        "home_win_prob": round(home_win * 100, 1),
        "draw_prob": round(draw * 100, 1),
        "away_win_prob": round(away_win * 100, 1),
        "over_2.5_prob": round(over_25 * 100, 1),
        "btts_prob": round(btts * 100, 1)
    }

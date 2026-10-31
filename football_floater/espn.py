"""ESPN soccer API URL helpers."""


def scoreboard_url(league_id):
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"


def summary_url(league_id):
    return f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/summary"

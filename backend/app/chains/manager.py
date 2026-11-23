from app.chains.score_chain import KeywordScoreChain, ScoreChain


def get_chain(name: str) -> ScoreChain:
    """Build a chain by name. LLM-backed chains are selected here when they are added."""
    if name == "score":
        return KeywordScoreChain()
    raise ValueError(f"Unknown chain: {name}")

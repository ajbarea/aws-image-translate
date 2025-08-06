"""Reddit configuration utilities for centralized subreddit management."""

import os
from typing import List


def get_subreddits_from_env() -> List[str]:
    """
    Get list of subreddits from environment variable.

    Returns:
        List of subreddit names from REDDIT_SUBREDDITS environment variable.
        Defaults to ["translator"] if not set or empty.
    """
    subreddits_env = os.environ.get("REDDIT_SUBREDDITS", "translator")

    if not subreddits_env or not subreddits_env.strip():
        return ["translator"]

    # Split by comma and clean up whitespace
    subreddits = [s.strip() for s in subreddits_env.split(",") if s.strip()]

    # Ensure we have at least one subreddit
    if not subreddits:
        return ["translator"]

    return subreddits


def get_default_subreddit() -> str:
    """
    Get the default/primary subreddit.

    Returns:
        The first subreddit from the configured list.
    """
    subreddits = get_subreddits_from_env()
    return subreddits[0]

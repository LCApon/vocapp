from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from database.model import Review

from fsrs import Scheduler, Card, Rating, State

# One scheduler instance, shared across the app
scheduler = Scheduler()

def convert_to_fsrs_card(review: Review) -> Card:
    """Reconstruct an fsrs.Card from the fields stored in the DB."""
    return Card(
        due=review.dt_due,
        stability=review.stability,
        difficulty=review.difficulty,
        state=State(review.state),
        step=review.step,
    )

def get_updated_card(
    review: Review,
    rating: int,
) -> Card:
    """
    Run the FSRS algorithm for a given rating.
    Mutates the review in-place with updated FSRS fields.
    Returns that updated Review entry.
    """
    fsrs_card = convert_to_fsrs_card(review)
    fsrs_rating = Rating(rating)

    updated_card, review_log = scheduler.review_card(
        fsrs_card,
        fsrs_rating,
        review_datetime=review.dt_last_review
    )

    return updated_card

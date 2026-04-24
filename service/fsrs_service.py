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
    )

def get_updated_review(
    review: Review,
    rating: int,
) -> Review:
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

    # Write updated FSRS state back onto the review
    review.dt_due = updated_card.due
    review.state = int(updated_card.state)
    if review.state == 1:
        review.lapses += 1
    review.step = updated_card.step
    review.stability = updated_card.stability
    review.difficulty = updated_card.difficulty
    review.reps += 1

    return review
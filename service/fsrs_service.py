from __future__ import annotations
from typing import TYPE_CHECKING, List
if TYPE_CHECKING:
    from database.model import Review, ReviewLog

from datetime import timedelta
from fsrs import Scheduler, Card, Rating, State, ReviewLog as ReviewLogFsrs

# One scheduler instance, shared across the app
scheduler = Scheduler(
    desired_retention=.92,
    learning_steps=(timedelta(minutes=10), timedelta(hours=1)),
    relearning_steps=(timedelta(hours=1), timedelta(days=1)),
)

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

def get_rescheduled_card(
    review: Review,
    lstReviewLog: List[ReviewLog]
) -> Card:
    fsrs_card = convert_to_fsrs_card(review)

    lstFsrsReviewLog = [ReviewLogFsrs(fsrs_card.card_id, Rating(row.rating), row.dt_review, None) for row in lstReviewLog]
    updated_card = scheduler.reschedule_card(fsrs_card, lstFsrsReviewLog)

    return updated_card

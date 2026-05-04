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

def convert_to_cardFsrs(review: Review) -> Card:
    """Reconstruct an fsrs.Card from the fields stored in the DB."""
    return Card(
        due=review.dtDue,
        stability=review.stability,
        difficulty=review.difficulty,
        state=State(review.state),
        step=review.step,
    )

def get_cardUpdated(
    review: Review,
    rating: int,
) -> Card:
    """
    Run the FSRS algorithm for a given rating.
    Mutates the review in-place with updated FSRS fields.
    Returns that updated Review entry.
    """
    cardFsrs = convert_to_cardFsrs(review)
    ratingFsrs = Rating(rating)

    cardUpdated, review_log = scheduler.review_card(
        cardFsrs,
        ratingFsrs,
        review_datetime=review.dtLastReview
    )

    return cardUpdated

def get_rescheduled_card(
    review: Review,
    lstReviewLog: List[ReviewLog]
) -> Card:
    cardFsrs = convert_to_cardFsrs(review)

    lstFsrsReviewLog = [ReviewLogFsrs(cardFsrs.card_id, Rating(row.rating), row.dtReview, None) for row in lstReviewLog]
    cardUpdated = scheduler.reschedule_card(cardFsrs, lstFsrsReviewLog)

    return cardUpdated

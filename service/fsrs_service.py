from fsrs import Scheduler, Card, Rating, State
from database.model import Translation, Review

# One scheduler instance, shared across the app
scheduler = Scheduler()

def translation_to_fsrs_card(translation: Translation) -> Card:
    """Reconstruct an fsrs.Card from the fields stored in the DB."""
    return Card(
        due=translation.dt_due,
        stability=translation.stability,
        difficulty=translation.difficulty,
        state=State(translation.state),
    )

def apply_review(
    translation: Translation,
    rating: int,
) -> Review:
    """
    Run the FSRS algorithm for a given rating.
    Mutates the translation in-place with updated FSRS fields.
    Returns an unsaved Review log entry.
    """
    fsrs_card = translation_to_fsrs_card(translation)
    fsrs_rating = Rating(rating)
    state_before = translation.state

    updated_card, review_log = scheduler.review_card(
        fsrs_card,
        fsrs_rating,
        review_datetime=translation.dt_last_review
    )

    # Write updated FSRS state back onto the translation
    translation.dt_due = updated_card.due
    translation.stability = updated_card.stability
    translation.difficulty = updated_card.difficulty
    translation.reps += 1
    if translation.state == 1:
        translation.lapses += 1
    translation.state = int(updated_card.state)

    # Build the review log row (not yet added to session)
    return Review(
        id_translation=translation.id,
        dt_review=review_log.review_datetime,
        rating=rating,
        state_before=state_before,
        stability=updated_card.stability,
        difficulty=updated_card.difficulty,
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from clarte360_ipip.framework.validation import ValidationError
from .model import Questionnaire

TOTAL_ITEMS = 120


@dataclass(frozen=True)
class QuestionPosition:
    item_no: int
    answered_count: int
    progress_ratio: float


def validate_item_no(item_no: int) -> int:
    n = int(item_no)
    if not 1 <= n <= TOTAL_ITEMS:
        raise ValidationError("Position de questionnaire invalide.")
    return n


def item_at(q: Questionnaire, item_no: int):
    n = validate_item_no(item_no)
    item = q.items[n - 1]
    if item.item_no != n:
        raise ValidationError("Ordre du référentiel incohérent.")
    return item


def first_unanswered(answers: Mapping[int, int], *, default: int = 1) -> int:
    for n in range(1, TOTAL_ITEMS + 1):
        if n not in answers:
            return n
    return validate_item_no(default)


def resume_item(answers: Mapping[int, int], saved_item: int | None = None) -> int:
    """Return the exact saved position when available, otherwise the first unanswered item."""
    if saved_item is not None:
        try:
            return validate_item_no(saved_item)
        except (TypeError, ValueError, ValidationError):
            pass
    return first_unanswered(answers, default=TOTAL_ITEMS)


def previous_item(item_no: int) -> int:
    return max(1, validate_item_no(item_no) - 1)


def next_item(item_no: int) -> int:
    return min(TOTAL_ITEMS, validate_item_no(item_no) + 1)


def position(item_no: int, answers: Mapping[int, int]) -> QuestionPosition:
    n = validate_item_no(item_no)
    answered = len({int(k) for k in answers if 1 <= int(k) <= TOTAL_ITEMS})
    return QuestionPosition(item_no=n, answered_count=answered, progress_ratio=n / TOTAL_ITEMS)

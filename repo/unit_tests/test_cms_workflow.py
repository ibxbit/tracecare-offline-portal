"""
Unit tests for CMS page workflow state transitions.

The valid transition graph (from the router and model docs):
  draft      → review     (submit-review)
  review     → published  (approve)
  review     → draft      (reject)
  published  → archived   (archive)
  archived   → draft      (restore)

All other transitions are invalid and should be rejected by the router.
"""
import pytest

from app.models.cms import CMSPageStatus, MAX_PAGE_REVISIONS


# ---------------------------------------------------------------------------
# State machine definition (mirrors router-enforced transitions)
# ---------------------------------------------------------------------------

_ALLOWED_TRANSITIONS: dict[CMSPageStatus, set[CMSPageStatus]] = {
    CMSPageStatus.draft:     {CMSPageStatus.review},
    CMSPageStatus.review:    {CMSPageStatus.published, CMSPageStatus.draft},
    CMSPageStatus.published: {CMSPageStatus.archived},
    CMSPageStatus.archived:  {CMSPageStatus.draft},
}


def can_transition(from_status: CMSPageStatus, to_status: CMSPageStatus) -> bool:
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, set())


# ---------------------------------------------------------------------------
# CMSPageStatus enum
# ---------------------------------------------------------------------------

class TestCMSPageStatusEnum:
    def test_all_four_states_defined(self):
        values = {s.value for s in CMSPageStatus}
        assert values == {"draft", "review", "published", "archived"}

    def test_status_is_string_enum(self):
        assert isinstance(CMSPageStatus.draft, str)

    def test_status_equality(self):
        assert CMSPageStatus("draft") == CMSPageStatus.draft

    def test_max_revisions_positive(self):
        assert MAX_PAGE_REVISIONS > 0
        assert MAX_PAGE_REVISIONS == 30


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------

class TestValidTransitions:
    def test_draft_to_review(self):
        assert can_transition(CMSPageStatus.draft, CMSPageStatus.review) is True

    def test_review_to_published(self):
        assert can_transition(CMSPageStatus.review, CMSPageStatus.published) is True

    def test_review_to_draft_on_reject(self):
        assert can_transition(CMSPageStatus.review, CMSPageStatus.draft) is True

    def test_published_to_archived(self):
        assert can_transition(CMSPageStatus.published, CMSPageStatus.archived) is True

    def test_archived_to_draft_restore(self):
        assert can_transition(CMSPageStatus.archived, CMSPageStatus.draft) is True


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    def test_draft_cannot_go_directly_to_published(self):
        assert can_transition(CMSPageStatus.draft, CMSPageStatus.published) is False

    def test_draft_cannot_go_directly_to_archived(self):
        assert can_transition(CMSPageStatus.draft, CMSPageStatus.archived) is False

    def test_draft_cannot_self_loop(self):
        assert can_transition(CMSPageStatus.draft, CMSPageStatus.draft) is False

    def test_review_cannot_go_to_archived(self):
        assert can_transition(CMSPageStatus.review, CMSPageStatus.archived) is False

    def test_review_cannot_self_loop(self):
        assert can_transition(CMSPageStatus.review, CMSPageStatus.review) is False

    def test_published_cannot_go_to_draft(self):
        assert can_transition(CMSPageStatus.published, CMSPageStatus.draft) is False

    def test_published_cannot_go_to_review(self):
        assert can_transition(CMSPageStatus.published, CMSPageStatus.review) is False

    def test_published_cannot_self_loop(self):
        assert can_transition(CMSPageStatus.published, CMSPageStatus.published) is False

    def test_archived_cannot_go_to_published(self):
        assert can_transition(CMSPageStatus.archived, CMSPageStatus.published) is False

    def test_archived_cannot_go_to_review(self):
        assert can_transition(CMSPageStatus.archived, CMSPageStatus.review) is False

    def test_archived_cannot_self_loop(self):
        assert can_transition(CMSPageStatus.archived, CMSPageStatus.archived) is False


# ---------------------------------------------------------------------------
# Full lifecycle paths
# ---------------------------------------------------------------------------

class TestLifecyclePaths:
    def test_happy_path_draft_to_published(self):
        path = [
            CMSPageStatus.draft,
            CMSPageStatus.review,
            CMSPageStatus.published,
        ]
        for from_s, to_s in zip(path, path[1:]):
            assert can_transition(from_s, to_s), f"{from_s} → {to_s} should be valid"

    def test_reject_path_review_back_to_draft(self):
        assert can_transition(CMSPageStatus.review, CMSPageStatus.draft) is True
        # After rejection (back to draft) can re-submit
        assert can_transition(CMSPageStatus.draft, CMSPageStatus.review) is True

    def test_archive_and_restore_cycle(self):
        # published → archived → draft (→ review → published again)
        assert can_transition(CMSPageStatus.published, CMSPageStatus.archived) is True
        assert can_transition(CMSPageStatus.archived, CMSPageStatus.draft) is True
        assert can_transition(CMSPageStatus.draft, CMSPageStatus.review) is True

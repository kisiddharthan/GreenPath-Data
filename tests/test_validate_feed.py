import copy
import unittest

from validation.validate_feed import (
    FeedValidationError,
    validate_feed,
)


def valid_feed() -> dict:
    return {
        "schemaVersion": 1,
        "generatedAt": "2026-07-29T20:30:00Z",
        "source": {
            "publisher": "U.S. Department of State",
            "bulletinType": "Employment-Based Visa Bulletin",
            "sourceURL": "https://travel.state.gov/",
            "retrievedAt": "2026-07-29T20:25:00Z",
        },
        "entries": [
            {
                "bulletinMonth": "2026-07-01",
                "category": "EB-2",
                "country": "India",
                "finalActionDate": "2013-02-15",
                "filingDate": "2013-03-01",
            }
        ],
    }


class ValidateFeedTests(unittest.TestCase):

    def test_valid_feed_passes(self) -> None:
        validate_feed(valid_feed())

    def test_empty_entries_fails(self) -> None:
        feed = valid_feed()
        feed["entries"] = []

        with self.assertRaisesRegex(
            FeedValidationError,
            "at least one",
        ):
            validate_feed(feed)

    def test_invalid_category_fails(self) -> None:
        feed = valid_feed()
        feed["entries"][0]["category"] = "EB2"

        with self.assertRaisesRegex(
            FeedValidationError,
            "unsupported",
        ):
            validate_feed(feed)

    def test_invalid_country_fails(self) -> None:
        feed = valid_feed()
        feed["entries"][0]["country"] = "IND"

        with self.assertRaisesRegex(
            FeedValidationError,
            "unsupported",
        ):
            validate_feed(feed)

    def test_invalid_cutoff_fails(self) -> None:
        feed = valid_feed()
        feed["entries"][0]["finalActionDate"] = "Soon"

        with self.assertRaisesRegex(
            FeedValidationError,
            "valid yyyy-MM-dd",
        ):
            validate_feed(feed)

    def test_current_cutoff_passes(self) -> None:
        feed = valid_feed()
        feed["entries"][0]["finalActionDate"] = "C"

        validate_feed(feed)

    def test_unavailable_cutoff_passes(self) -> None:
        feed = valid_feed()
        feed["entries"][0]["finalActionDate"] = "U"

        validate_feed(feed)

    def test_duplicate_entry_fails(self) -> None:
        feed = valid_feed()
        feed["entries"].append(
            copy.deepcopy(feed["entries"][0])
        )

        with self.assertRaisesRegex(
            FeedValidationError,
            "Duplicate",
        ):
            validate_feed(feed)

    def test_non_first_day_bulletin_month_fails(self) -> None:
        feed = valid_feed()
        feed["entries"][0]["bulletinMonth"] = "2026-07-15"

        with self.assertRaisesRegex(
            FeedValidationError,
            "first day",
        ):
            validate_feed(feed)

    def test_generated_before_retrieved_fails(self) -> None:
        feed = valid_feed()
        feed["generatedAt"] = "2026-07-29T20:00:00Z"
        feed["source"]["retrievedAt"] = (
            "2026-07-29T20:25:00Z"
        )

        with self.assertRaisesRegex(
            FeedValidationError,
            "cannot be earlier",
        ):
            validate_feed(feed)


if __name__ == "__main__":
    unittest.main()

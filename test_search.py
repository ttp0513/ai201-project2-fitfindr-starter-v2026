"""Regression tests for the deterministic listing-search rules."""

import unittest

from tools import search_listings


class SearchListingsTests(unittest.TestCase):
    def test_multi_word_search_removes_one_word_matches(self):
        results = search_listings("90s track jacket", size="M", max_price=60)

        self.assertEqual(
            [item["title"] for item in results],
            ["90s Track Jacket — Navy/White Stripe"],
        )

    def test_denim_jacket_does_not_return_other_denim_items(self):
        results = search_listings("denim jacket", max_price=50)

        self.assertEqual(
            [item["title"] for item in results],
            ["Denim Jacket — Light Wash, Cropped"],
        )

    def test_single_word_search_still_requires_only_one_match(self):
        results = search_listings("jacket", max_price=50)

        self.assertTrue(results)
        self.assertTrue(any("Jacket" in item["title"] for item in results))

    def test_empty_search_still_returns_an_empty_list(self):
        self.assertEqual(
            search_listings("designer ballgown", size="XXS", max_price=5),
            [],
        )

    def test_every_result_respects_the_price_ceiling(self):
        results = search_listings("platform sneakers", size="US 8", max_price=60)

        self.assertTrue(results)
        self.assertTrue(all(item["price"] <= 60 for item in results))


if __name__ == "__main__":
    unittest.main()

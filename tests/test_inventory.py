import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from labloop.contracts import InventoryItem
from labloop.inventory import InventoryStore


class InventoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temporary_directory.name) / "inventory.db"
        self.store = InventoryStore(self.db_path)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def item(
        item_id="tips",
        name="Pipette tips",
        quantity=10.0,
        unit="box",
        threshold=2.0,
        order_quantity=5.0,
    ):
        return InventoryItem(
            item_id, name, quantity, unit, threshold, order_quantity
        )

    def test_upsert_and_complete_round_trip(self):
        original = self.item()
        updated = self.item(name="Filtered tips", quantity=8, threshold=3, order_quantity=6)

        self.store.upsert_item(original)
        self.assertEqual(self.store.get_item(original.id), original)
        self.store.upsert_item(updated)

        self.assertEqual(self.store.get_item(original.id), updated)
        self.assertIsNone(self.store.get_item("missing"))

    def test_list_items_has_deterministic_case_insensitive_order(self):
        for item in (
            self.item("b", "alpha"),
            self.item("c", "Beta"),
            self.item("a", "Alpha"),
        ):
            self.store.upsert_item(item)

        self.assertEqual([item.id for item in self.store.list_items()], ["a", "b", "c"])

    def test_normal_consumption_does_not_create_request(self):
        self.store.upsert_item(self.item())

        updated, request = self.store.consume("tips", 3, " BOX ")

        self.assertEqual(updated.quantity, 7)
        self.assertIsNone(request)
        self.assertEqual(self.store.get_item("tips"), updated)
        self.assertEqual(self.store.list_purchase_requests(), [])

    def test_exact_threshold_creates_correct_pending_request(self):
        self.store.upsert_item(self.item())

        updated, request = self.store.consume("tips", 8, "box")

        self.assertEqual(updated.quantity, 2)
        self.assertIsNotNone(request)
        self.assertEqual(request.item_id, "tips")
        self.assertEqual(request.quantity, 5)
        self.assertEqual(request.unit, "box")
        self.assertEqual(request.status, "pending")
        self.assertTrue(request.created_at.endswith("Z"))
        self.assertEqual(self.store.list_purchase_requests(), [request])

    def test_repeated_consumption_does_not_duplicate_pending_request(self):
        self.store.upsert_item(self.item())
        _, first = self.store.consume("tips", 8, "box")

        _, second = self.store.consume("tips", 1, "box")

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(self.store.list_purchase_requests(), [first])

    def test_below_threshold_with_only_history_creates_pending_request(self):
        self.store.upsert_item(self.item(quantity=2))
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO purchase_requests
                    (id, item_id, quantity, unit, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("old", "tips", 5, "box", "approved", "2020-01-01T00:00:00Z"),
            )

        _, request = self.store.consume("tips", 1, "box")

        self.assertEqual(request.status, "pending")
        self.assertEqual(len(self.store.list_purchase_requests()), 2)

    def test_invalid_consumption_fails_without_changing_stock(self):
        self.store.upsert_item(self.item())
        invalid_calls = (
            ("tips", 1, "case"),
            ("tips", 0, "box"),
            ("tips", -1, "box"),
            ("tips", True, "box"),
            ("tips", math.inf, "box"),
            ("tips", math.nan, "box"),
            ("missing", 1, "box"),
            ("tips", 11, "box"),
        )

        for arguments in invalid_calls:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.store.consume(*arguments)

        self.assertEqual(self.store.get_item("tips"), self.item())
        self.assertEqual(self.store.list_purchase_requests(), [])

    def test_failed_request_insert_rolls_back_quantity_update(self):
        self.store.upsert_item(self.item())
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_request BEFORE INSERT ON purchase_requests
                BEGIN SELECT RAISE(ABORT, 'forced request failure'); END
                """
            )

        with self.assertRaisesRegex(ValueError, "forced request failure"):
            self.store.consume("tips", 8, "box")

        self.assertEqual(self.store.get_item("tips"), self.item())
        self.assertEqual(self.store.list_purchase_requests(), [])

    def test_status_filtering_treats_injection_text_as_a_value(self):
        self.store.upsert_item(self.item())
        _, pending = self.store.consume("tips", 8, "box")
        injection_text = "pending' OR 1=1 --"
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO purchase_requests
                    (id, item_id, quantity, unit, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("old", "tips", 1, "box", "approved", "2020-01-01T00:00:00Z"),
            )
            connection.execute(
                """
                INSERT INTO purchase_requests
                    (id, item_id, quantity, unit, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("text", "tips", 1, "box", injection_text, "2021-01-01T00:00:00Z"),
            )

        self.assertEqual(self.store.list_purchase_requests("pending"), [pending])
        self.assertEqual(
            [request.id for request in self.store.list_purchase_requests()],
            [pending.id, "text", "old"],
        )
        self.assertEqual(
            [request.id for request in self.store.list_purchase_requests(injection_text)],
            ["text"],
        )
        with self.assertRaises(ValueError):
            self.store.list_purchase_requests("  ")

    def test_item_validation_rejects_invalid_boundaries(self):
        invalid_items = (
            self.item(item_id=""),
            self.item(name=" "),
            self.item(unit=""),
            self.item(quantity=True),
            self.item(quantity=math.inf),
            self.item(quantity=-1),
            self.item(threshold=-1),
            self.item(order_quantity=0),
        )

        for item in invalid_items:
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.store.upsert_item(item)

        self.assertEqual(self.store.list_items(), [])


if __name__ == "__main__":
    unittest.main()

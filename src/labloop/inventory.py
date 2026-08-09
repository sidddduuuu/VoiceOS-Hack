"""SQLite-backed inventory tracking and pending restock requests."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import astuple
from datetime import datetime, timezone
import math
from pathlib import Path
import sqlite3
from typing import Iterator
import uuid

from .contracts import InventoryItem, PurchaseRequest


class InventoryStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        with self._transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory_items (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK (quantity >= 0),
                    unit TEXT NOT NULL,
                    reorder_threshold REAL NOT NULL CHECK (reorder_threshold >= 0),
                    preferred_order_quantity REAL NOT NULL
                        CHECK (preferred_order_quantity > 0)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS purchase_requests (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES inventory_items(id),
                    quantity REAL NOT NULL CHECK (quantity > 0),
                    unit TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS one_pending_request_per_item
                ON purchase_requests(item_id) WHERE status = 'pending'
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(f"inventory constraint failed: {error}") from error
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    def upsert_item(self, item: InventoryItem) -> None:
        self._validate_item(item)
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO inventory_items
                    (id, name, quantity, unit, reorder_threshold,
                     preferred_order_quantity)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    quantity = excluded.quantity,
                    unit = excluded.unit,
                    reorder_threshold = excluded.reorder_threshold,
                    preferred_order_quantity = excluded.preferred_order_quantity
                """,
                (
                    item.id,
                    item.name,
                    item.quantity,
                    item.unit,
                    item.reorder_threshold,
                    item.preferred_order_quantity,
                ),
            )

    def get_item(self, item_id: str) -> InventoryItem | None:
        self._nonempty(item_id, "item ID")
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, name, quantity, unit, reorder_threshold,
                       preferred_order_quantity
                FROM inventory_items WHERE id = ?
                """,
                (item_id,),
            ).fetchone()
        return self._item(row) if row else None

    def list_items(self) -> list[InventoryItem]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, name, quantity, unit, reorder_threshold,
                       preferred_order_quantity
                FROM inventory_items
                """
            ).fetchall()
        return sorted(
            (self._item(row) for row in rows),
            key=lambda item: (item.name.casefold(), item.id),
        )

    def consume(
        self, item_id: str, amount: float, unit: str
    ) -> tuple[InventoryItem, PurchaseRequest | None]:
        self._nonempty(item_id, "item ID")
        self._number(amount, "amount", positive=True)
        self._nonempty(unit, "unit")

        with self._transaction() as connection:
            row = connection.execute(
                """SELECT id, name, quantity, unit, reorder_threshold,
                          preferred_order_quantity
                   FROM inventory_items WHERE id = ?""",
                (item_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown inventory item: {item_id}")

            item = self._item(row)
            if item.unit.strip().casefold() != unit.strip().casefold():
                raise ValueError(f"unit must match {item.unit!r}")
            remaining = item.quantity - amount
            if remaining < 0:
                raise ValueError("consumption would make inventory negative")

            connection.execute(
                "UPDATE inventory_items SET quantity = ? WHERE id = ?",
                (remaining, item_id),
            )
            request = None
            if remaining <= item.reorder_threshold:
                pending = connection.execute(
                    """SELECT 1 FROM purchase_requests
                       WHERE item_id = ? AND status = 'pending'""",
                    (item_id,),
                ).fetchone()
                if pending is None:
                    request = PurchaseRequest(
                        id=str(uuid.uuid4()),
                        item_id=item_id,
                        quantity=item.preferred_order_quantity,
                        unit=item.unit,
                        status="pending",
                        created_at=self._timestamp(),
                    )
                    connection.execute(
                        """INSERT INTO purchase_requests
                               (id, item_id, quantity, unit, status, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        astuple(request),
                    )

        return InventoryItem(
            id=item.id,
            name=item.name,
            quantity=remaining,
            unit=item.unit,
            reorder_threshold=item.reorder_threshold,
            preferred_order_quantity=item.preferred_order_quantity,
        ), request

    def list_purchase_requests(
        self, status: str | None = None
    ) -> list[PurchaseRequest]:
        if status is not None:
            self._nonempty(status, "status")
        query = """
            SELECT id, item_id, quantity, unit, status, created_at
            FROM purchase_requests
        """
        parameters: tuple[str, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            parameters = (status,)
        query += " ORDER BY created_at DESC, id"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [PurchaseRequest(*row) for row in rows]

    @classmethod
    def _validate_item(cls, item: InventoryItem) -> None:
        if not isinstance(item, InventoryItem):
            raise ValueError("item must be an InventoryItem")
        cls._nonempty(item.id, "item ID")
        cls._nonempty(item.name, "item name")
        cls._nonempty(item.unit, "unit")
        cls._number(item.quantity, "quantity", nonnegative=True)
        cls._number(item.reorder_threshold, "reorder threshold", nonnegative=True)
        cls._number(
            item.preferred_order_quantity,
            "preferred order quantity",
            positive=True,
        )

    @staticmethod
    def _nonempty(value: object, field: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")

    @staticmethod
    def _number(
        value: object,
        field: str,
        *,
        positive: bool = False,
        nonnegative: bool = False,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a finite number")
        if not math.isfinite(value):
            raise ValueError(f"{field} must be a finite number")
        if positive and value <= 0:
            raise ValueError(f"{field} must be positive")
        if nonnegative and value < 0:
            raise ValueError(f"{field} must not be negative")

    @staticmethod
    def _item(row: tuple[object, ...]) -> InventoryItem:
        return InventoryItem(*row)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

"""
Generic Base Repository Implementation for CyberScout AI.

Provides reusable CRUD operations, bulk actions, pagination, and SQL query helpers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar

from src.database.connection import DatabaseManager
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class BaseRepository(Generic[T], ABC):
    """
    Abstract Base Repository encapsulating common SQLite CRUD operations.
    """

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Database table name associated with this repository."""
        pass

    @property
    @abstractmethod
    def primary_key(self) -> str:
        """Primary key column name (defaults to 'id')."""
        return "id"

    @abstractmethod
    def _entity_to_dict(self, entity: T) -> Dict[str, Any]:
        """Converts domain entity object to database record dictionary."""
        pass

    @abstractmethod
    def _row_to_entity(self, row: Any) -> T:
        """Converts database row object to domain entity instance."""
        pass

    def create(self, entity: T) -> str:
        """
        Inserts a single entity record into the database.

        Args:
            entity: Domain model entity.

        Returns:
            Inserted primary key ID string.
        """
        data = self._entity_to_dict(entity)
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        values = tuple(data[c] for c in columns)

        sql = f"INSERT INTO {self.table_name} ({col_names}) VALUES ({placeholders});"

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
            record_id = str(data.get(self.primary_key, ""))
            logger.debug(f"Inserted record '{record_id}' into '{self.table_name}'.")
            return record_id
        except Exception as e:
            raise RepositoryError(f"Failed to create record in '{self.table_name}': {e}", original_exception=e)

    def read_by_id(self, record_id: str) -> Optional[T]:
        """
        Reads a single record by primary key ID.

        Args:
            record_id: Target record primary key string.

        Returns:
            Domain entity object if found, None otherwise.
        """
        sql = f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?;"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (record_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_entity(row)
            return None
        finally:
            cursor.close()

    def update(self, entity: T) -> bool:
        """
        Updates an existing record matching primary key ID.

        Args:
            entity: Domain model entity.

        Returns:
            True if record was updated, False if not found.
        """
        data = self._entity_to_dict(entity)
        record_id = data.get(self.primary_key)
        if not record_id:
            raise RepositoryError(f"Missing primary key '{self.primary_key}' for update in '{self.table_name}'.")

        update_cols = [c for c in data.keys() if c != self.primary_key]
        set_clause = ", ".join([f"{col} = ?" for col in update_cols])
        values = tuple(data[c] for c in update_cols) + (record_id,)

        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.primary_key} = ?;"

        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, values)
                updated = cursor.rowcount > 0
            return updated
        except Exception as e:
            raise RepositoryError(f"Failed to update record '{record_id}' in '{self.table_name}': {e}", original_exception=e)

    def delete(self, record_id: str) -> bool:
        """
        Deletes a record matching primary key ID.

        Args:
            record_id: Target record primary key string.

        Returns:
            True if record was deleted, False otherwise.
        """
        sql = f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?;"
        try:
            with self.db_manager.transaction() as cursor:
                cursor.execute(sql, (record_id,))
                deleted = cursor.rowcount > 0
            return deleted
        except Exception as e:
            raise RepositoryError(f"Failed to delete record '{record_id}' from '{self.table_name}': {e}", original_exception=e)

    def exists(self, record_id: str) -> bool:
        """Checks if a record matching primary key ID exists."""
        sql = f"SELECT 1 FROM {self.table_name} WHERE {self.primary_key} = ?;"
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (record_id,))
            row = cursor.fetchone()
            return row is not None
        finally:
            cursor.close()

    def count(self, where_clause: str = "", params: Tuple[Any, ...] = ()) -> int:
        """Returns count of records matching optional WHERE clause."""
        sql = f"SELECT COUNT(*) as cnt FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        sql += ";"

        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return row["cnt"] if row else 0
        finally:
            cursor.close()

    def search(
        self,
        where_clause: str = "",
        params: Tuple[Any, ...] = (),
        order_by: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> List[T]:
        """
        Searches records using customizable WHERE, ORDER BY, LIMIT, and OFFSET clauses.

        Args:
            where_clause: Optional SQL WHERE condition.
            params: Tuple of query parameter values.
            order_by: Optional SQL ORDER BY clause.
            limit: Maximum records to return.
            offset: Record offset for pagination.

        Returns:
            List of domain entity objects.
        """
        sql = f"SELECT * FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        sql += f" LIMIT {limit} OFFSET {offset};"

        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [self._row_to_entity(row) for row in rows]
        finally:
            cursor.close()

    def bulk_insert(self, entities: List[T]) -> int:
        """
        Inserts multiple entity records in a single database transaction.

        Args:
            entities: List of domain entities.

        Returns:
            Count of inserted records.
        """
        if not entities:
            return 0

        first_data = self._entity_to_dict(entities[0])
        columns = list(first_data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        sql = f"INSERT INTO {self.table_name} ({col_names}) VALUES ({placeholders});"

        rows_data = [tuple(self._entity_to_dict(e)[c] for c in columns) for e in entities]

        try:
            with self.db_manager.transaction() as cursor:
                cursor.executemany(sql, rows_data)
            logger.info(f"Bulk inserted {len(entities)} records into '{self.table_name}'.")
            return len(entities)
        except Exception as e:
            raise RepositoryError(f"Bulk insert failed for '{self.table_name}': {e}", original_exception=e)

    def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
        where_clause: str = "",
        params: Tuple[Any, ...] = (),
        order_by: str = "",
    ) -> Tuple[List[T], int]:
        """
        Returns a paginated result tuple (items, total_count).

        Args:
            page: 1-indexed page number.
            page_size: Number of records per page.
            where_clause: Optional WHERE clause.
            params: Tuple of WHERE parameters.
            order_by: Optional ORDER BY clause.

        Returns:
            Tuple of (list_of_entities, total_count).
        """
        total_count = self.count(where_clause, params)
        offset = (page - 1) * page_size
        items = self.search(
            where_clause=where_clause,
            params=params,
            order_by=order_by,
            limit=page_size,
            offset=offset,
        )
        return items, total_count

"""
Neo4j connection client with async query execution, retry logic, and structured logging.

Wraps the official neo4j Python driver. All queries must be parameterised — never
interpolate user data into Cypher strings.
"""

import os
from typing import Any

import structlog
from neo4j import AsyncGraphDatabase, AsyncDriver
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

log = structlog.get_logger(__name__)

_RETRY_EXCEPTIONS = (ServiceUnavailable, SessionExpired, ConnectionError)


class Neo4jClient:
    """Async Neo4j driver wrapper with connection lifecycle management and retry logic.

    Uses a class-level shared driver so all ``async with Neo4jClient()`` calls
    reuse the same connection pool instead of opening a new one each time.
    This prevents connection exhaustion on AuraDB free tier.
    """

    # Shared driver reused across all instances
    _shared_driver: AsyncDriver | None = None

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """
        Initialise the client using env vars by default.

        Args:
            uri: Neo4j bolt URI. Defaults to NEO4J_URI env var.
            username: Database username. Defaults to NEO4J_USERNAME env var.
            password: Database password. Defaults to NEO4J_PASSWORD env var.
        """
        self._uri = uri or os.environ["NEO4J_URI"]
        self._username = username or os.environ["NEO4J_USERNAME"]
        self._password = password or os.environ["NEO4J_PASSWORD"]
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Attach to the shared driver, creating it if this is the first call."""
        if Neo4jClient._shared_driver is None:
            Neo4jClient._shared_driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password),
                max_connection_pool_size=10,
            )
            await Neo4jClient._shared_driver.verify_connectivity()
            log.info("neo4j.connected", uri=self._uri)
        self._driver = Neo4jClient._shared_driver

    async def close(self) -> None:
        """Release this instance's reference. Does NOT close the shared pool."""
        self._driver = None
        log.info("neo4j.closed")

    @classmethod
    async def close_shared_driver(cls) -> None:
        """Close the shared connection pool. Call once at application shutdown."""
        if cls._shared_driver is not None:
            await cls._shared_driver.close()
            cls._shared_driver = None
            log.info("neo4j.driver_shutdown")

    @retry(
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        before_sleep=before_sleep_log(log, "warning"),  # type: ignore[arg-type]
    )
    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return all rows as a list of dicts.

        Args:
            query: Parameterised Cypher query string.
            params: Dictionary of query parameters.

        Returns:
            List of result rows, each as a plain dict.

        Raises:
            RuntimeError: If the client has not been connected yet.
        """
        if self._driver is None:
            raise RuntimeError("Neo4jClient is not connected. Call connect() first.")

        params = params or {}
        async with self._driver.session() as session:
            result = await session.run(query, params)
            records = await result.data()
            log.debug(
                "neo4j.query_executed",
                rows=len(records),
                query_preview=query[:80],
            )
            return records

    async def __aenter__(self) -> "Neo4jClient":
        """Support use as an async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        """Close on context manager exit."""
        await self.close()

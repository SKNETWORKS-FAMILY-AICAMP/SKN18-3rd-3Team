"""PostgreSQL connection management with connection pooling"""

import psycopg
from psycopg_pool import ConnectionPool
from typing import Optional
from contextlib import contextmanager

from rag.core.logger import get_logger


logger = get_logger(__name__)


class DatabaseConnection:
    """
    Database connection manager with connection pooling.
    
    Usage:
        db = DatabaseConnection(db_url)
        with db.get_connection() as conn:
            # use connection
            pass
    """
    
    def __init__(self, db_url: str, min_size: int = 2, max_size: int = 10):
        """
        Initialize connection pool.
        
        Args:
            db_url: PostgreSQL connection URL
            min_size: Minimum number of connections in pool
            max_size: Maximum number of connections in pool
        """
        print(f"[DEBUG] DatabaseConnection.__init__ called", flush=True)
        
        print(f"[DEBUG] Setting attributes...", flush=True)
        self.db_url = db_url
        self.min_size = min_size
        self.max_size = max_size
        self._pool: Optional[ConnectionPool] = None
        
        print(f"[DEBUG] DatabaseConnection configured successfully", flush=True)
        logger.info(f"Database connection pool configured (min={min_size}, max={max_size}) - will connect on first use")
    
    def _initialize_pool(self):
        """Initialize the connection pool lazily"""
        if self._pool is not None:
            return
        
        try:
            logger.info("Connecting to database...")
            self._pool = ConnectionPool(
                conninfo=self.db_url,
                min_size=self.min_size,
                max_size=self.max_size,
                timeout=30,
                open=False  # Don't open connections immediately
            )
            # Open the pool when needed
            self._pool.open()
            logger.info("Database connection pool opened successfully")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    
    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool (context manager).
        
        Yields:
            psycopg.Connection: Database connection
        """
        # Lazy initialization
        if self._pool is None:
            self._initialize_pool()
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            bool: True if connection is healthy
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    return result is not None and result[0] == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def close(self):
        """Close the connection pool"""
        if self._pool:
            self._pool.close()
            logger.info("Database connection pool closed")

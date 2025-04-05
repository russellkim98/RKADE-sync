"""SQLite database management for tracking operations and results."""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd


class Database:
    """Database manager for the music matcher application."""

    def __init__(self, db_path: str):
        """Initialize database connection and create tables if they don't exist.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create table for tracking runs
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                status TEXT NOT NULL,
                config TEXT NOT NULL,
                stats TEXT
            )
            """
            )

            # Create table for tracking individual track matches
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS track_matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                spotify_track_id TEXT NOT NULL,
                youtube_track_id TEXT,
                match_score REAL,
                matcher_used TEXT NOT NULL,
                match_time TIMESTAMP NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                spotify_data TEXT NOT NULL,
                youtube_data TEXT,
                FOREIGN KEY (run_id) REFERENCES runs (run_id)
            )
            """
            )

            # Create table for tracking LLM queries
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS llm_queries (
                query_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                track_match_id INTEGER,
                query_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT,
                execution_time REAL NOT NULL,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                query_time TIMESTAMP NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs (run_id),
                FOREIGN KEY (track_match_id) REFERENCES track_matches (match_id)
            )
            """
            )

            # Create table for logging
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                timestamp TIMESTAMP NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs (run_id)
            )
            """
            )

            conn.commit()

    def start_run(self, config: Dict[str, Any]) -> int:
        """Start a new tracking run.

        Args:
            config: Dictionary containing configuration for this run

        Returns:
            run_id: ID of the newly created run
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO runs (start_time, status, config) VALUES (?, ?, ?)",
                (datetime.now(), "RUNNING", json.dumps(config)),
            )
            conn.commit()
            if not isinstance(cursor.lastrowid, int):
                raise Exception("Database last row id is not an integer.")
            return cursor.lastrowid

    def end_run(
        self, run_id: int, status: str, stats: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark a run as complete with final statistics.

        Args:
            run_id: ID of the run to finish
            status: Final status (SUCCESS, FAILED, etc.)
            stats: Optional statistics about the run
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE runs SET end_time = ?, status = ?, stats = ? WHERE run_id = ?",
                (datetime.now(), status, json.dumps(stats) if stats else None, run_id),
            )
            conn.commit()

    def log_track_match(
        self,
        run_id: int,
        spotify_track_id: str,
        spotify_data: Dict[str, Any],
        youtube_track_id: Optional[str] = None,
        youtube_data: Optional[Dict[str, Any]] = None,
        match_score: Optional[float] = None,
        matcher_used: str = "fuzzy",
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> int:
        """Log a track matching operation.

        Args:
            run_id: ID of the current run
            spotify_track_id: Spotify track ID
            spotify_data: Full Spotify track data
            youtube_track_id: YouTube track ID if found
            youtube_data: Full YouTube track data if found
            match_score: Score of the match if applicable
            matcher_used: Which matcher was used (fuzzy, llm, etc.)
            success: Whether the operation was successful
            error_message: Error message if unsuccessful

        Returns:
            match_id: ID of the newly created track match record
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO track_matches (
                    run_id, spotify_track_id, youtube_track_id, match_score,
                    matcher_used, match_time, success, error_message,
                    spotify_data, youtube_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    spotify_track_id,
                    youtube_track_id,
                    match_score,
                    matcher_used,
                    datetime.now(),
                    success,
                    error_message,
                    json.dumps(spotify_data),
                    json.dumps(youtube_data) if youtube_data else None,
                ),
            )
            conn.commit()
            if not isinstance(cursor.lastrowid, int):
                raise Exception("Database last row id is not an integer.")
            return cursor.lastrowid

    def log_llm_query(
        self,
        run_id: int,
        query_type: str,
        prompt: str,
        execution_time: float,
        success: bool,
        response: Optional[str] = None,
        error_message: Optional[str] = None,
        track_match_id: Optional[int] = None,
    ) -> int:
        """Log an LLM query.

        Args:
            run_id: ID of the current run
            query_type: Type of query (search, judge, etc.)
            prompt: Prompt sent to the LLM
            execution_time: Time taken to execute the query in seconds
            success: Whether the query was successful
            response: Response from the LLM if successful
            error_message: Error message if unsuccessful
            track_match_id: ID of the related track match if applicable

        Returns:
            query_id: ID of the newly created LLM query record
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO llm_queries (
                    run_id, track_match_id, query_type, prompt, response,
                    execution_time, success, error_message, query_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    track_match_id,
                    query_type,
                    prompt,
                    response,
                    execution_time,
                    success,
                    error_message,
                    datetime.now(),
                ),
            )
            conn.commit()

            if not isinstance(cursor.lastrowid, int):
                raise Exception("Database last row id is not an integer.")
            return cursor.lastrowid

    def add_log(self, level: str, message: str, run_id: Optional[int] = None) -> None:
        """Add a log entry.

        Args:
            level: Log level (DEBUG, INFO, etc.)
            message: Log message
            run_id: Optional ID of the current run
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO logs (run_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
                (run_id, datetime.now(), level, message),
            )
            conn.commit()

    def get_runs(self) -> pd.DataFrame:
        """Get all runs as a DataFrame.

        Returns:
            DataFrame containing all runs
        """
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query("SELECT * FROM runs", conn)

    def get_track_matches(self, run_id: Optional[int] = None) -> pd.DataFrame:
        """Get track matches as a DataFrame.

        Args:
            run_id: Optional ID to filter by specific run

        Returns:
            DataFrame containing track matches
        """
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM track_matches"
            if run_id is not None:
                query += f" WHERE run_id = {run_id}"
            return pd.read_sql_query(query, conn)

    def get_llm_queries(self, run_id: Optional[int] = None) -> pd.DataFrame:
        """Get LLM queries as a DataFrame.

        Args:
            run_id: Optional ID to filter by specific run

        Returns:
            DataFrame containing LLM queries
        """
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM llm_queries"
            if run_id is not None:
                query += f" WHERE run_id = {run_id}"
            return pd.read_sql_query(query, conn)

    def get_logs(
        self, run_id: Optional[int] = None, level: Optional[str] = None
    ) -> pd.DataFrame:
        """Get logs as a DataFrame.

        Args:
            run_id: Optional ID to filter by specific run
            level: Optional log level to filter by

        Returns:
            DataFrame containing logs
        """
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM logs"
            conditions = []

            if run_id is not None:
                conditions.append(f"run_id = {run_id}")
            if level is not None:
                conditions.append(f"level = '{level}'")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            return pd.read_sql_query(query, conn)

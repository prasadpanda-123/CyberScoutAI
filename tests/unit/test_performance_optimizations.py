import gzip
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import time
import unittest
from uuid import uuid4
from unittest.mock import patch

from flask import Flask, Response, request, send_file

from dashboard.app import optimize_static_asset
from dashboard.sessions import PostgresSessionInterface, ServerSideSession
from src.database.connection import DatabaseManager, PgConnectionAdapter
from src.database.opportunity_repository import OpportunityRepository
from src.database.session_repository import hash_session_id
from src.database.user_preferences_repository import UserPreferencesRepository
from src.models.query_filter_dto import QueryFilterDTO


class TestPerformanceOptimizations(unittest.TestCase):
    def test_pool_adapter_returns_connection_once(self):
        class PoolProxy:
            closed = False

            def __init__(self):
                self.close_calls = 0

            def close(self):
                self.close_calls += 1

        proxy = PoolProxy()
        connection = PgConnectionAdapter(proxy)
        connection.close()
        connection.close()

        self.assertEqual(proxy.close_calls, 1)
        self.assertTrue(connection.closed)

    def test_health_metrics_use_two_round_trips_and_close_connection(self):
        class Cursor:
            def __init__(self):
                self.queries = []
                self.rows = [
                    {"version": "PostgreSQL 16.2, compiled by test", "table_names": ["Users", "Opportunities"]},
                    {"Users": 8, "Opportunities": 12},
                ]
                self.closed = False

            def execute(self, query):
                self.queries.append(query)

            def fetchone(self):
                return self.rows.pop(0)

            def close(self):
                self.closed = True

        class Connection:
            def __init__(self):
                self.query_cursor = Cursor()
                self.closed = False

            def cursor(self):
                return self.query_cursor

            def rollback(self):
                pass

            def close(self):
                self.closed = True

        manager = DatabaseManager(custom_url="postgresql://user:pass@localhost/db")
        connection = Connection()
        manager.get_connection = lambda: connection

        metrics = manager.get_health_metrics()

        self.assertTrue(metrics["connected"])
        self.assertEqual(metrics["tables"], 2)
        self.assertEqual(metrics["table_counts"], {"Opportunities": 12, "Users": 8})
        self.assertEqual(len(connection.query_cursor.queries), 2)
        self.assertTrue(connection.query_cursor.closed)
        self.assertTrue(connection.closed)

    def test_feed_uses_window_count_saved_join_and_single_facet_query(self):
        class Cursor:
            description = None

            def __init__(self):
                self.queries = []
                self.results = [
                    [{
                        "id": "opp-1",
                        "title": "Opportunity",
                        "total_count": 1,
                        "is_saved": True,
                    }],
                    [{"facet": "categories", "value": "security", "cnt": 4}],
                ]

            def execute(self, query, parameters=()):
                self.queries.append((query, parameters))

            def fetchall(self):
                return self.results.pop(0)

            def close(self):
                pass

        class Connection:
            def __init__(self):
                self.query_cursor = Cursor()
                self.closed = False

            def cursor(self):
                return self.query_cursor

            def close(self):
                self.closed = True

        manager = DatabaseManager(custom_url="postgresql://user:pass@localhost/db")
        connection = Connection()
        manager.get_connection = lambda: connection
        repository = OpportunityRepository(manager)
        user_id = str(uuid4())

        items, total_count, facets = repository.query_opportunities(
            QueryFilterDTO(category="security", user_id=user_id)
        )

        self.assertEqual(total_count, 1)
        self.assertNotIn("total_count", items[0])
        self.assertTrue(items[0]["is_saved"])
        self.assertEqual(facets["categories"], {"security": 4})
        self.assertEqual(len(connection.query_cursor.queries), 2)
        page_query, parameters = connection.query_cursor.queries[0]
        self.assertIn("COUNT(*) OVER()", page_query)
        self.assertIn('LEFT JOIN "SavedOpportunities" so', page_query)
        self.assertEqual(parameters[0], user_id)
        self.assertTrue(connection.closed)

    def test_empty_saved_page_keeps_total_and_join_parameters_in_order(self):
        class Cursor:
            description = None

            def __init__(self):
                self.queries = []
                self.results = [[], []]

            def execute(self, query, parameters=()):
                self.queries.append((query, parameters))

            def fetchall(self):
                return self.results.pop(0)

            def fetchone(self):
                return (3,)

            def close(self):
                pass

        class Connection:
            def __init__(self):
                self.query_cursor = Cursor()

            def cursor(self):
                return self.query_cursor

            def close(self):
                pass

        manager = DatabaseManager(custom_url="postgresql://user:pass@localhost/db")
        connection = Connection()
        manager.get_connection = lambda: connection
        repository = OpportunityRepository(manager)
        user_id = str(uuid4())

        items, total_count, _ = repository.query_opportunities(
            QueryFilterDTO(category="security", user_id=user_id, saved_only=True)
        )

        self.assertEqual(items, [])
        self.assertEqual(total_count, 3)
        self.assertIn('INNER JOIN "SavedOpportunities" so', connection.query_cursor.queries[0][0])
        self.assertEqual(connection.query_cursor.queries[0][1], (user_id, "security", 24, 0))
        self.assertIn("SELECT COUNT(*)", connection.query_cursor.queries[1][0])
        self.assertEqual(connection.query_cursor.queries[1][1], (user_id, "security"))

    def test_personalization_preferences_and_behavior_use_one_query(self):
        class Cursor:
            description = None

            def __init__(self, user_id):
                self.user_id = user_id
                self.queries = []
                self.closed = False

            def execute(self, query, parameters=()):
                self.queries.append((query, parameters))

            def fetchone(self):
                return {
                    "preference_user_id": self.user_id,
                    "skills": '["Python"]',
                    "interests": "[]",
                    "preferred_categories": "[]",
                    "preferred_types": "[]",
                    "saved_behavior": (
                        '[{"tags":"[\\"CTF\\"]","category":"Research",'
                        '"opportunity_type":"scholarship"}]'
                    ),
                }

            def close(self):
                self.closed = True

        class Connection:
            def __init__(self, user_id):
                self.query_cursor = Cursor(user_id)
                self.closed = False

            def cursor(self):
                return self.query_cursor

            def close(self):
                self.closed = True

        user_id = str(uuid4())
        manager = DatabaseManager(custom_url="postgresql://user:pass@localhost/db")
        connection = Connection(user_id)
        manager.get_connection = lambda: connection
        repository = UserPreferencesRepository(manager)

        preferences, behavior = repository.get_personalization_data(user_id)

        self.assertIsNotNone(preferences)
        assert preferences is not None
        self.assertEqual(preferences.skills, ["python"])
        self.assertEqual(behavior, (["ctf"], ["research", "scholarship"]))
        self.assertEqual(len(connection.query_cursor.queries), 1)
        self.assertEqual(connection.query_cursor.queries[0][1], (user_id, user_id))
        self.assertTrue(connection.closed)

    def test_static_assets_are_compressed_and_fingerprinted_assets_cached(self):
        app = Flask(__name__)
        body = b"const bundle = 'performance optimization';\n" * 100

        with app.test_request_context(
            "/static/react/assets/index-AbCdEf1234.js",
            headers={"Accept-Encoding": "gzip"},
        ):
            response = optimize_static_asset(
                send_file(BytesIO(body), mimetype="application/javascript")
            )

        self.assertEqual(response.headers["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(response.get_data()), body)
        self.assertEqual(
            response.headers["Cache-Control"],
            "public, max-age=31536000, immutable",
        )
        self.assertIn("Accept-Encoding", response.headers["Vary"])
        self.assertTrue(response.get_etag()[0])

    def test_static_requests_skip_session_io_and_do_not_issue_cookie(self):
        app = Flask(__name__)
        app.config["SESSION_COOKIE_NAME"] = "cyberscout_session"
        interface = PostgresSessionInterface()

        with app.test_request_context(
            "/static/react/assets/index.js",
            headers={"Cookie": "cyberscout_session=opaque-session-id"},
        ):
            session = interface.open_session(app, request)
            response = Response()
            interface.save_session(app, session, response)

        self.assertTrue(session._skip_persistence)
        self.assertIsNone(response.headers.get("Set-Cookie"))

    def test_concurrent_first_requests_initialize_session_repository_once(self):
        interface = PostgresSessionInterface()
        created = object()

        def create_repo():
            time.sleep(0.01)
            return created

        with patch("dashboard.sessions.SessionRepository", side_effect=create_repo) as repo_factory:
            with ThreadPoolExecutor(max_workers=8) as executor:
                repos = list(executor.map(lambda _: interface._get_repo(), range(16)))

        self.assertTrue(all(repo is created for repo in repos))
        repo_factory.assert_called_once()

    def test_logout_deletes_database_session_and_test_cache_entry(self):
        class SessionRepository:
            def __init__(self):
                self.deleted = []

            def delete_session(self, session_hash):
                self.deleted.append(session_hash)

        repo = SessionRepository()
        interface = PostgresSessionInterface(repo)
        sid = "opaque-session-id-that-is-long-enough"
        session_hash = hash_session_id(sid)
        interface._in_memory_sessions[session_hash] = {"csrf_token": "token"}
        session = ServerSideSession({"csrf_token": "token"}, sid=sid)
        session.clear()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SESSION_COOKIE_NAME"] = "cyberscout_session"

        with app.test_request_context("/logout"):
            response = Response()
            interface.save_session(app, session, response)

        self.assertEqual(repo.deleted, [session_hash])
        self.assertNotIn(session_hash, interface._in_memory_sessions)
        self.assertIn("cyberscout_session=", response.headers["Set-Cookie"])

    def test_logout_surfaces_revocation_failure_and_clears_test_cache(self):
        class SessionRepository:
            def delete_session(self, session_hash):
                raise RuntimeError("session store unavailable")

        interface = PostgresSessionInterface(SessionRepository())
        sid = "opaque-session-id-for-failed-revocation"
        session_hash = hash_session_id(sid)
        interface._in_memory_sessions[session_hash] = {"csrf_token": "token"}
        session = ServerSideSession({"csrf_token": "token"}, sid=sid)
        session.clear()
        app = Flask(__name__)
        app.config["SESSION_COOKIE_NAME"] = "cyberscout_session"

        with app.test_request_context("/logout"):
            with self.assertRaisesRegex(RuntimeError, "session store unavailable"):
                interface.save_session(app, session, Response())

        self.assertNotIn(session_hash, interface._in_memory_sessions)


if __name__ == "__main__":
    unittest.main()

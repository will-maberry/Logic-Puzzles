"""Contract checks for API-only puzzle play and hostile JSON inputs."""

import asyncio
import json
import unittest
from unittest.mock import patch

from main import app
from games.queens_logic import find_queen_solutions


async def direct_call(func, *args, **kwargs):
    """Run sync FastAPI endpoints in this in-process ASGI test client."""
    return func(*args, **kwargs)


async def request(path, payload, client_host="127.0.0.1"):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.sleep(3600)

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "path": path, "raw_path": path.encode(),
        "query_string": b"", "root_path": "", "scheme": "http",
        "headers": [(b"content-type", b"application/json")],
        "client": (client_host, 1234), "server": ("127.0.0.1", 8000),
    }
    await app(scope, receive, send)
    status = next(message["status"] for message in sent if message["type"] == "http.response.start")
    data = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    return status, json.loads(data) if data.startswith((b"{", b"[")) else data


class APIContractTests(unittest.TestCase):
    def call(self, path, payload, client_host="127.0.0.1"):
        with patch("fastapi.routing.run_in_threadpool", direct_call), \
             patch("starlette.middleware.exceptions.run_in_threadpool", direct_call):
            return asyncio.run(request(path, payload, client_host))

    def test_generated_solutions_win_at_original_difficulties(self):
        for size in (4, 6, 8, 10):
            with self.subTest(size=size):
                status, puzzle = self.call("/api/queens/generate", {"size": size})
                self.assertEqual(status, 200)
                self.assertEqual(puzzle["size"], size)
                self.assertEqual(len(find_queen_solutions(puzzle["regions"])), 1)
                board = [[0] * size for _ in range(size)]
                for row, col in enumerate(puzzle["solution"]):
                    board[row][col] = 1
                status, result = self.call("/api/queens/check", {
                    "size": size, "board": board, "regions": puzzle["regions"]
                })
                self.assertEqual(status, 200)
                self.assertTrue(result["win"])

    def test_rejects_unwashed_generate_inputs(self):
        for payload in ({"size": "6"}, {"size": True}, {"size": 6.0},
                        {"size": 6, "script": "<script>alert(1)</script>"},
                        {"size": 11}, {"size": 20}, {"size": 1000000}):
            with self.subTest(payload=payload):
                self.assertEqual(self.call("/api/queens/generate", payload)[0], 422)

    def test_rejects_unwashed_move_inputs(self):
        regions = [[0, 1, 2, 3] for _ in range(4)]
        board = [[0] * 4 for _ in range(4)]
        for change in ({"board": [["1", 0, 0, 0]] + board[1:]},
                       {"regions": [[0, 1, 2, True]] + regions[1:]},
                       {"board": board[:-1]},
                       {"extra": "<img src=x onerror=alert(1)>"}):
            self.assertEqual(self.call("/api/queens/check", {"size": 4, "board": board, "regions": regions, **change})[0], 422)

    def test_body_limit(self):
        self.assertEqual(self.call("/api/queens/generate", b"x" * 16385)[0], 413)

    def test_conflicting_moves_are_checked_by_api(self):
        regions = [[0, 1, 2, 3] for _ in range(4)]
        board = [[1, 1, 0, 0]] + [[0] * 4 for _ in range(3)]
        status, result = self.call("/api/queens/check", {"size": 4, "board": board, "regions": regions})
        self.assertEqual(status, 200)
        self.assertFalse(result["win"])
        self.assertIn([0, 0], result["conflicts"])
        self.assertIn([0, 1], result["conflicts"])

    def test_slowapi_generation_limit(self):
        regions = [[0, 1, 2, 3] for _ in range(4)]
        with patch("games.queens.generate_queen_solution", return_value=[1, 3, 0, 2]), \
             patch("games.queens.generate_regions", return_value=regions), \
             patch("games.queens.carve_regions", return_value=regions), \
             patch("games.queens.find_queen_solutions", return_value=[[1, 3, 0, 2]]):
            statuses = [self.call("/api/queens/generate", {"size": 4}, "192.0.2.10")[0]
                        for _ in range(21)]
        self.assertEqual(statuses[:20], [200] * 20)
        self.assertEqual(statuses[20], 429)

    def test_tents_api_is_removed(self):
        self.assertEqual(self.call("/api/tents/generate", {"size": 6})[0], 404)


if __name__ == "__main__":
    unittest.main()

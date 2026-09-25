import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from embodied.api import WorkbenchHandler


class WorkbenchApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), WorkbenchHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_evidence_read_model(self) -> None:
        with urlopen(self.base + "/api/overview", timeout=3) as response:
            overview = json.load(response)
        self.assertEqual(overview["summary"]["count"], 64)
        self.assertEqual(len(overview["catalog"]["interfaces"]), 11)
        with urlopen(self.base + "/api/runs/mission-000", timeout=3) as response:
            record = json.load(response)
        self.assertEqual(record["payload"]["outcome"], "SUCCESS")

    def test_only_development_fixture_can_run(self) -> None:
        request = Request(
            self.base + "/api/missions",
            data=b'{"scenario_id":"mission-000"}',
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            record = json.load(response)
        self.assertEqual(record["payload"]["outcome"], "SUCCESS")
        rejected = Request(
            self.base + "/api/missions",
            data=b'{"scenario_id":"mission-064"}',
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as context:
            urlopen(rejected, timeout=3)
        self.assertEqual(context.exception.code, 400)


if __name__ == "__main__":
    unittest.main()

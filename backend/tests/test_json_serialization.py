import unittest
import datetime
from pathlib import Path
from decimal import Decimal
from uuid import UUID
import json
from backend.app.core.json_util import make_json_serializable

class TestJSONSerialization(unittest.TestCase):
    def test_primitives(self):
        self.assertEqual(make_json_serializable(123), 123)
        self.assertEqual(make_json_serializable("hello"), "hello")
        self.assertEqual(make_json_serializable(True), True)
        self.assertIsNone(make_json_serializable(None))

    def test_dates_and_datetimes(self):
        dt = datetime.datetime(2026, 7, 9, 15, 30, 0)
        d = datetime.date(2026, 7, 9)
        self.assertEqual(make_json_serializable(dt), "2026-07-09T15:30:00")
        self.assertEqual(make_json_serializable(d), "2026-07-09")

    def test_custom_objects(self):
        path = Path("/home/user/test.txt")
        dec = Decimal("123.45")
        u = UUID("12345678-1234-5678-1234-567812345678")
        
        self.assertEqual(make_json_serializable(path), "/home/user/test.txt")
        self.assertEqual(make_json_serializable(dec), 123.45)
        self.assertEqual(make_json_serializable(u), "12345678-1234-5678-1234-567812345678")

    def test_containers(self):
        s = {1, 2, 3}
        t = (4, 5, 6)
        self.assertEqual(make_json_serializable(s), [1, 2, 3])
        self.assertEqual(make_json_serializable(t), [4, 5, 6])

    def test_nested_structures(self):
        nested = {
            "date": datetime.date(2026, 7, 9),
            "datetime": datetime.datetime(2026, 7, 9, 10, 0, 0),
            "path": Path("/var/log"),
            "decimal": Decimal("9.99"),
            "uuid": UUID("87654321-4321-4321-4321-210987654321"),
            "set_val": {10, 20},
            "tuple_val": (datetime.date(2026, 1, 1), "text"),
            "list_val": [
                {"nested_date": datetime.date(2026, 5, 5)}
            ]
        }
        
        serialized = make_json_serializable(nested)
        
        # Verify it serializes with standard json.dumps without throwing TypeError
        dumped = json.dumps(serialized)
        self.assertTrue(isinstance(dumped, str))
        
        # Verify values
        self.assertEqual(serialized["date"], "2026-07-09")
        self.assertEqual(serialized["datetime"], "2026-07-09T10:00:00")
        self.assertEqual(serialized["path"], "/var/log")
        self.assertEqual(serialized["decimal"], 9.99)
        self.assertEqual(serialized["uuid"], "87654321-4321-4321-4321-210987654321")
        self.assertEqual(serialized["set_val"], [10, 20])
        self.assertEqual(serialized["tuple_val"], ["2026-01-01", "text"])
        self.assertEqual(serialized["list_val"][0]["nested_date"], "2026-05-05")

if __name__ == "__main__":
    unittest.main()

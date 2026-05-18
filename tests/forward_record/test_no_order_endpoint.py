from __future__ import annotations

import unittest
from pathlib import Path

from apps.forward_record.safety import scan_no_order_endpoints


class NoOrderEndpointTest(unittest.TestCase):
    def test_forward_record_runtime_has_no_order_endpoint_terms(self) -> None:
        scan = scan_no_order_endpoints([Path("apps/forward_record"), Path("scripts/run_forward_record.py")])
        self.assertEqual(scan["status"], "PASS")
        self.assertEqual(scan["violations"], [])


if __name__ == "__main__":
    unittest.main()


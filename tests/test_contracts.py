import unittest

from labloop.contracts import ExpectedRange, Protocol, ProtocolStep


class ContractTests(unittest.TestCase):
    def test_expected_range_handles_open_bounds(self) -> None:
        self.assertTrue(ExpectedRange(minimum=1).contains(2))
        self.assertFalse(ExpectedRange(maximum=1).contains(2))

    def test_protocol_is_immutable(self) -> None:
        protocol = Protocol(
            id="demo",
            name="Demo",
            version="1",
            steps=(ProtocolStep("step-1", "Start", "Begin"),),
        )
        with self.assertRaises(AttributeError):
            protocol.name = "Changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()

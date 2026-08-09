import math
import unittest

from labloop.contracts import ExpectedRange, Measurement, ProtocolStep, Severity
from labloop.validation import validate_measurement


def measurement(**changes: object) -> Measurement:
    values = {
        "run_id": "run-1",
        "step_id": "step-1",
        "sample_id": "sample-1",
        "value": 5.0,
        "unit": "mL",
        "instrument": "pipette-1",
        "conditions": {"temperature": "22 C"},
        "captured_at": "2026-08-09T12:00:00Z",
    }
    values.update(changes)
    return Measurement(**values)  # type: ignore[arg-type]


class ValidationTests(unittest.TestCase):
    def test_complete_in_range_measurement_has_no_issues(self) -> None:
        step = ProtocolStep(
            "step-1",
            "Measure",
            "Record volume",
            required_fields=("sample_id", "value", "unit", "instrument", "captured_at"),
            expected_unit="mL",
            expected_range=ExpectedRange(0, 10),
        )

        self.assertEqual(validate_measurement(step, measurement()), [])

    def test_missing_supported_fields_follow_protocol_order(self) -> None:
        fields = (
            "captured_at",
            "condition.temperature",
            "sample_id",
            "value",
            "unit",
            "instrument",
        )
        step = ProtocolStep("step-1", "Measure", "Record", required_fields=fields)
        result = validate_measurement(
            step,
            measurement(
                captured_at=" ",
                conditions={"temperature": ""},
                sample_id=None,
                value=None,
                unit="\t",
                instrument=None,
            ),
        )

        self.assertEqual([issue.field for issue in result], list(fields))
        self.assertTrue(all(issue.severity is Severity.BLOCKING for issue in result))
        self.assertTrue(all(issue.question.endswith("?") for issue in result))

    def test_value_must_be_finite_numeric_and_zero_is_present(self) -> None:
        step = ProtocolStep("step-1", "Measure", "Record", required_fields=("value",))
        self.assertEqual(validate_measurement(step, measurement(value=0)), [])

        for value in (math.nan, math.inf, -math.inf, True, False):
            with self.subTest(value=value):
                result = validate_measurement(step, measurement(value=value))
                self.assertEqual([issue.field for issue in result], ["value"])
                self.assertEqual(result[0].severity, Severity.BLOCKING)

    def test_condition_fields_do_not_mutate_input(self) -> None:
        conditions = {"temperature": " ", "humidity": 0}
        original = conditions.copy()
        step = ProtocolStep(
            "step-1",
            "Measure",
            "Record",
            required_fields=("condition.temperature", "condition.humidity"),
        )

        result = validate_measurement(step, measurement(conditions=conditions))

        self.assertEqual([issue.field for issue in result], ["condition.temperature"])
        self.assertEqual(conditions, original)

    def test_units_ignore_case_and_whitespace_but_incompatible_units_block(self) -> None:
        step = ProtocolStep("step-1", "Measure", "Record", expected_unit="mL")
        self.assertEqual(validate_measurement(step, measurement(unit=" ML ")), [])

        result = validate_measurement(step, measurement(unit="uL"))
        self.assertEqual([issue.field for issue in result], ["unit"])
        self.assertEqual(result[0].severity, Severity.BLOCKING)

    def test_range_bounds_are_inclusive(self) -> None:
        step = ProtocolStep(
            "step-1", "Measure", "Record", expected_range=ExpectedRange(1, 10)
        )
        self.assertEqual(validate_measurement(step, measurement(value=1)), [])
        self.assertEqual(validate_measurement(step, measurement(value=10)), [])
        self.assertEqual(
            validate_measurement(step, measurement(value=0))[0].severity,
            Severity.WARNING,
        )
        self.assertEqual(
            validate_measurement(step, measurement(value=11))[0].severity,
            Severity.WARNING,
        )

    def test_out_of_range_warning_is_non_diagnostic(self) -> None:
        step = ProtocolStep(
            "step-1", "Measure", "Record", expected_range=ExpectedRange(1, 10)
        )

        issue = validate_measurement(step, measurement(value=11))[0]

        self.assertEqual(issue.field, "value")
        self.assertEqual(issue.severity, Severity.WARNING)
        self.assertIn("Recorded value 11", issue.question)
        self.assertIn("approved protocol range 1 to 10", issue.question)
        for forbidden in ("cause", "because", "remedy", "continue", "adjust"):
            self.assertNotIn(forbidden, issue.question.casefold())

    def test_step_identifiers_and_unsupported_fields_block_first(self) -> None:
        step = ProtocolStep(
            "step-1", "Measure", "Record", required_fields=("unsupported_field",)
        )

        result = validate_measurement(
            step, measurement(run_id=" ", step_id="other-step")
        )

        self.assertEqual(
            [issue.field for issue in result],
            ["step_id", "run_id", "unsupported_field"],
        )
        self.assertTrue(all(issue.severity is Severity.BLOCKING for issue in result))
        self.assertIn("unsupported metadata", result[-1].question)

        empty_step = ProtocolStep("", "Measure", "Record")
        empty_result = validate_measurement(empty_step, measurement(step_id=""))
        self.assertEqual([issue.field for issue in empty_result], ["step_id"])


if __name__ == "__main__":
    unittest.main()

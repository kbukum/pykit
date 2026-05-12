"""JUnit XML report generation."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykit_bench.result import BenchRunResult


class JUnitReporter:
    """Generates JUnit XML where metrics with targets become test cases."""

    @property
    def name(self) -> str:
        return "junit"

    def generate(self, writer: io.StringIO, result: BenchRunResult) -> None:
        """Write JUnit XML report to *writer*."""
        testsuites = ET.Element("testsuites")
        testsuite = ET.SubElement(
            testsuites,
            "testsuite",
            name=f"bench-{result.id}",
            tests=str(len(result.metrics)),
            timestamp=result.timestamp.isoformat(),
            time=f"{result.duration_ms / 1000:.3f}",
        )

        for m in result.metrics:
            testcase = ET.SubElement(
                testsuite,
                "testcase",
                classname=f"bench.{result.dataset.name}",
                name=m.name,
                time="0",
            )

            # Attach metric value as system-out
            system_out = ET.SubElement(testcase, "system-out")
            lines = [f"value={m.value:.4f}"]
            for k, v in m.values.items():
                lines.append(f"{k}={v:.4f}")
            system_out.text = "\n".join(lines)

            # Treat value == 0 as a failure for non-trivial metrics
            if m.value == 0.0 and m.values:
                failure = ET.SubElement(
                    testcase,
                    "failure",
                    message=f"{m.name} scored 0.0",
                    type="MetricFailure",
                )
                failure.text = f"Metric {m.name} returned 0.0"

        tree = ET.ElementTree(testsuites)
        ET.indent(tree, space="  ")
        buf = io.StringIO()
        tree.write(buf, encoding="unicode", xml_declaration=True)
        writer.write(buf.getvalue())

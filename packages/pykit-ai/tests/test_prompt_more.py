from __future__ import annotations

from pykit_ai.prompt import Template, VariableDecl


def test_template_validate_output() -> None:
    template = Template(
        name="json",
        version="1.0.0",
        template="{{value}}",
        variables=[VariableDecl(name="value")],
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
    )
    assert template.validate_output({"ok": True}).valid
    assert not template.validate_output({"ok": "yes"}).valid

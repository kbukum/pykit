"""Structured output parsing — extract typed data from LLM text responses."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import TypeAdapter, ValidationError

from pykit_llm.types import CompletionResponse, TextBlock

T = TypeVar("T")

_JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


class ParseError(Exception):
    """Raised when structured output cannot be parsed from LLM text."""

    def __init__(self, message: str, *, raw_text: str = "") -> None:
        super().__init__(message)
        self.raw_text = raw_text


class StructuredOutput[T]:
    """Parse LLM text output into structured types.

    Uses Pydantic ``TypeAdapter`` for validation. Supports extracting JSON
    from markdown code blocks (````json ... ````) and plain JSON text.

    Args:
        output_type: The target type for parsing (dataclass, Pydantic model, etc.).
        strict: When ``True``, use Pydantic strict mode for validation.
    """

    def __init__(self, output_type: type[T], *, strict: bool = True) -> None:
        self._output_type = output_type
        self._strict = strict
        self._adapter: TypeAdapter[T] = TypeAdapter(output_type)

    def parse(self, text: str) -> T:
        """Parse text (expected JSON) into the target type.

        Handles markdown code blocks by extracting the JSON content first.

        Args:
            text: Raw text from the LLM, possibly wrapped in code blocks.

        Returns:
            An instance of the target type.

        Raises:
            ParseError: If the text cannot be parsed as valid JSON or
                fails type validation.
        """
        extracted = self._extract_json(text)
        try:
            data = json.loads(extracted)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Invalid JSON: {exc}", raw_text=text) from exc

        try:
            return self._adapter.validate_python(data, strict=self._strict)
        except ValidationError as exc:
            raise ParseError(f"Validation failed: {exc}", raw_text=text) from exc

    def parse_from_response(self, response: CompletionResponse) -> T:
        """Extract and parse structured output from an LLM response.

        Concatenates all ``TextBlock`` content from the response message
        and parses it.

        Args:
            response: The completion response from an LLM provider.

        Returns:
            An instance of the target type.

        Raises:
            ParseError: If no text content is found or parsing fails.
        """
        parts = [b.text for b in response.message.content if isinstance(b, TextBlock)]
        if not parts:
            raise ParseError("No text content in response", raw_text="")
        return self.parse("".join(parts))

    def system_instruction(self) -> str:
        """Generate a system instruction telling the LLM to output in the expected format.

        Returns:
            A system prompt string describing the expected JSON schema.
        """
        schema = self._adapter.json_schema()
        return (
            "You must respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```\n"
            "Do not include any text outside the JSON object."
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from text, handling markdown code blocks.

        Args:
            text: Raw text potentially containing a JSON code block.

        Returns:
            The extracted JSON string.
        """
        match = _JSON_BLOCK_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        return text.strip()

"""Fuzz test for pykit-errors ProblemDetail serialization."""

import sys

import atheris

with atheris.instrument_imports():
    from pykit_errors import AppError, ErrorCode


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    try:
        message = fdp.ConsumeUnicodeNoSurrogates(200)
        instance = fdp.ConsumeUnicodeNoSurrogates(100)
        code = fdp.PickValueInList(list(ErrorCode))
        err = AppError(code, message)
        pd = err.to_problem_detail(instance=instance)
        d = pd.to_dict()
        # Ensure serialization is stable
        assert isinstance(d["type"], str)
        assert isinstance(d["status"], int)
    except (ValueError, AttributeError):
        pass  # acceptable — crash (SIGFPE, SIGSEGV etc.) is NOT acceptable


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()

# Fuzzing

pykit uses [atheris](https://github.com/google/atheris) for coverage-guided fuzzing.

## Running a fuzz target

```bash
pip install atheris
python fuzz/fuzz_errors.py -runs=10000
```

## CI fuzzing

Fuzz jobs run in `.github/workflows/security.yml` (scheduled weekly).

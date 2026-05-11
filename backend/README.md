# LongNovelInsight Backend

## Setup

```bash
conda activate LongNovelInsight
cd backend
pip install -e ".[dev]"
```

## Run

```bash
uvicorn main:app --reload --port 8000
```

Access at `http://localhost:8000/api/health`.

## Test

```bash
python -m pytest -v
```

## Lint & Format

```bash
python -m ruff check .
python -m ruff format --check .
```

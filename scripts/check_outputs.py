"""Check latest analysis run outputs to understand content structure."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlmodel import Session, select
from db import engine
from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun

with Session(engine) as session:
    run = session.exec(
        select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    ).first()
    if not run:
        print("No runs found")
        sys.exit(1)

    print(f"Run: {run.id} status={run.status} mode={run.mode}")
    print(f"  tokens={run.total_tokens}")
    print(f"  extraction: {run.extraction_succeeded}/{run.extraction_total}")
    print(f"  merge: {run.merge_succeeded}/{run.merge_total}")
    print(f"  final: {run.final_succeeded}/{run.final_total}")

    outputs = session.exec(
        select(AnalysisOutput).where(AnalysisOutput.run_id == run.id)
    ).all()

    print(f"\nOutputs: {len(outputs)}")
    for o in outputs:
        cj = o.content_json
        print(f"\n  type={o.output_type} title={o.title}")
        print(f"  content_json len={len(cj)}")
        print(f"  content_json preview: {cj[:500]}")

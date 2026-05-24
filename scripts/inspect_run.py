"""Inspect atoms and merge outputs for a run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlmodel import Session, select
from db import engine
from models.extracted_atom import ExtractedAtom
from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun


def inspect(tid):
    with Session(engine) as session:
        # Get latest succeeded run for this topic
        runs = session.exec(
            select(AnalysisRun)
            .where(AnalysisRun.topic_id == tid)
            .order_by(AnalysisRun.created_at.desc())
        ).all()
        if not runs:
            print("No runs found")
            return
        run = runs[0]
        print(f"Run: {run.id} status={run.status} mode={run.mode}")
        print(f"  extraction: {run.extraction_succeeded}/{run.extraction_total}")
        print(f"  merge: {run.merge_succeeded}/{run.merge_total}")
        print(f"  final: {run.final_succeeded}/{run.final_total}")

        # Atoms
        atoms = session.exec(
            select(ExtractedAtom).where(ExtractedAtom.run_id == run.id)
        ).all()
        print(f"\nAtoms: {len(atoms)}")
        for a in atoms[:5]:
            print(f"  type={a.atom_type} stable_id={a.stable_id} content_len={len(a.content_json)}")

        # All outputs
        outputs = session.exec(
            select(AnalysisOutput).where(AnalysisOutput.run_id == run.id)
        ).all()
        print(f"\nOutputs: {len(outputs)}")
        for o in outputs:
            cj = o.content_json
            is_artifact = "__artifact__" in cj if isinstance(cj, str) else False
            print(f"  type={o.output_type} title={o.title} cj_len={len(cj)} artifact={is_artifact}")
            print(f"    preview: {cj[:300]}")

        # Check metadata
        meta = run.get_metadata()
        print(f"\nMetadata keys: {list(meta.keys())}")
        merge_summaries = meta.get("merge_summaries", [])
        print(f"Merge summaries: {merge_summaries}")
        final_summaries = meta.get("final_summaries", [])
        print(f"Final summaries: {final_summaries}")

        # Check warnings
        for w in meta.get("warnings", []):
            print(f"  Warning: {w}")


if __name__ == "__main__":
    # Use the topic ID from the integration test
    tid = sys.argv[1] if len(sys.argv) > 1 else "28421064-8f08-431b-8db2-bab7339cc8d4"
    inspect(tid)

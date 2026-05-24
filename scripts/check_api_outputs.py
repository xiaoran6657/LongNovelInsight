"""Check raw API response for the outputs of a run."""
import httpx

BASE = "http://127.0.0.1:8000"

client = httpx.Client(timeout=30, base_url=BASE)

# Check health
r = client.get("/api/health")
print(f"Health: {r.json()}")

# Get topics
r = client.get("/api/topics")
topics = r.json()["topics"]
print(f"Topics: {len(topics)}")

if topics:
    tid = topics[0]["id"]
    print(f"Using topic: {topics[0]['name']} ({tid[:8]}...)")

    # Get runs for this topic
    r = client.get(f"/api/topics/{tid}/analysis/runs")
    runs = r.json()["runs"]
    print(f"\nRuns: {len(runs)}")

    if runs:
        run = runs[0]
        rid = run["id"]
        print(f"Latest run: {rid} status={run['status']}")

        # Get full status (includes outputs)
        r = client.get(f"/api/analysis/runs/{rid}")
        status = r.json()

        print(f"\nRun status: {status['run']['status']}")
        print(f"  extraction: {status['run']['extraction_succeeded']}/{status['run']['extraction_total']}")
        print(f"  tokens: {status['run']['total_tokens']}")

        final = status.get("final", {})
        print(f"\nFinal outputs: {len(final.get('outputs', []))}")
        for fo in final.get("outputs", []):
            print(f"  output: id={fo['id']} type={fo.get('output_type')} title={fo.get('title')}")

            # Get individual output
            r2 = client.get(f"/api/analysis/outputs/{fo['id']}")
            raw = r2.json()
            # Print all keys
            print(f"    keys: {list(raw.keys())}")
            # Check content
            cj = raw.get("content_json", "MISSING")
            if isinstance(cj, str):
                print(f"    content_json(str) len={len(cj)}: {cj[:300]}")
            elif isinstance(cj, (dict, list)):
                print(f"    content_json(dict/list) keys/len={len(cj)}: {str(cj)[:300]}")
            else:
                print(f"    content_json type={type(cj)}: {str(cj)[:300]}")
            # Check for content_text or other fields
            ct = raw.get("content_text", raw.get("content", "NOT_PRESENT"))
            if ct != "NOT_PRESENT":
                print(f"    content_text: {str(ct)[:300]}")

client.close()

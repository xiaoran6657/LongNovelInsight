# ID Rules (shared by all analysis prompts)

Do not generate random UUIDs.
For chunk-level or batch-level extraction, use *_id_hint fields (e.g., character_id_hint, event_id_hint) rather than final database IDs.
The backend will canonicalize hints into stable IDs.
For final merge outputs, produce stable, lowercase, ASCII slug-like IDs derived from content:
- Event IDs: from concise event titles (e.g., "diary_started" from "保仁开始写日记").
- Character IDs: from canonical names using pinyin or a short semantic slug if already established.
If unsure, leave ID fields null or use an id_hint field.
Never fabricate IDs that refer to entities not present in the input.

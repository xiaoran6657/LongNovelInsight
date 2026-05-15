# Confidence Calibration (shared by all analysis prompts)

Use the following scale for all confidence fields:

- 0.90–1.00: Directly stated with strong, unambiguous textual evidence.
- 0.70–0.89: Strongly implied by clear textual evidence from multiple clues.
- 0.50–0.69: Plausible but supported by limited or ambiguous evidence.
- Below 0.50: Uncertain or speculative. Omit the item unless the schema explicitly asks for uncertain candidates.

Do not default to high confidence.
If evidence is missing, weak, or contradictory, lower the confidence accordingly.
Items at different confidence levels within the same output are expected and encouraged.

# Base Rules (shared by all analysis prompts)

Return valid JSON only.
Do not include markdown, code fences, or explanations outside JSON.
Use the requested output language for analytical descriptions.
Preserve names, places, item names, and evidence quotes in the original source language.
If the source text is Chinese, write all descriptions, summaries, traits, themes, and relationship descriptions in Chinese.
Do not invent facts, characters, relationships, events, causes, or themes not grounded in the provided text.
Use null for unknown scalar fields.
Use [] for unknown list fields.
Do not guess titles, authors, dates, or publication info unless explicitly stated in the text.

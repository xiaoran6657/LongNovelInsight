from enum import StrEnum


class AnalysisType(StrEnum):
    OVERVIEW = "overview"
    CHARACTERS = "characters"
    RELATIONS = "relations"
    EVENTS = "events"
    CAUSALITY = "causality"
    THEMES = "themes"


class JobType(StrEnum):
    PARSE = "parse"
    ANALYSIS = "analysis"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"


class JobItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class TopicStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    PARSED = "parsed"
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"


class AnalysisMode(StrEnum):
    PREVIEW = "preview"
    RANGE = "range"
    FULL = "full"
    INCREMENTAL = "incremental"


class AtomType(StrEnum):
    CHARACTER = "character"
    EVENT = "event"
    RELATION = "relation"
    CAUSAL_LINK = "causal_link"
    THEME_SIGNAL = "theme_signal"
    WORLDBUILDING = "worldbuilding"
    FORESHADOWING = "foreshadowing"
    OPEN_QUESTION = "open_question"


class WorkStatus(StrEnum):
    EMPTY = "empty"
    UPLOADED = "uploaded"
    PARSED = "parsed"
    ANALYZED = "analyzed"
    ERROR = "error"


class EntityType(StrEnum):
    CHARACTER = "character"
    LOCATION = "location"
    ORGANIZATION = "organization"
    CONCEPT = "concept"
    ITEM = "item"
    UNKNOWN = "unknown"


class CrossWorkRunMode(StrEnum):
    FULL = "full"
    ENTITIES_ONLY = "entities_only"
    GRAPH_ONLY = "graph_only"
    TIMELINE_ONLY = "timeline_only"

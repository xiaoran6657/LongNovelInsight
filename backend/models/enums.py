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

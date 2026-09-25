from enum import StrEnum


class MockDesiredStatus(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"


class MockRuntimeStatus(StrEnum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


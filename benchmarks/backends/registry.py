"""Backend factory for benchmark runners."""

from __future__ import annotations

from typing import Literal

from benchmarks.backends.condensate import CondensateBackend
from benchmarks.backends.full_context import FullContextBackend
from benchmarks.backends.observations import ObservationsBackend
from benchmarks.backends.structured import StructuredMemoryBackend

BackendName = Literal["full_context", "structured", "observations", "condensate"]

ALL_BACKENDS: tuple[BackendName, ...] = (
    "full_context",
    "structured",
    "observations",
    "condensate",
)


def build_backend(name: BackendName):
    if name == "full_context":
        return FullContextBackend()
    if name == "structured":
        return StructuredMemoryBackend()
    if name == "observations":
        return ObservationsBackend()
    if name == "condensate":
        return CondensateBackend()
    raise ValueError(f"Unknown backend: {name}")

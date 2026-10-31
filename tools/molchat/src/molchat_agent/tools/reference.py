"""Opt-in capabilities for the synthetic reference backend, not scientific data."""

from .catalog import Capability, EpistemicClass, FieldSpec, register

register(Capability(
    "reference_status", "Read a synthetic example record", "GET",
    "/reference/records/{record_id}",
    {"record_id": FieldSpec(str, max_length=32, pattern=r"[a-z0-9-]+")}, {},
    path_fields=("record_id",), epistemic_class=EpistemicClass.PERSISTED,
    provenance="reference backend: synthetic records", outputs=("record_id", "label"),
))
register(Capability(
    "reference_count", "Read the synthetic operation count", "GET",
    "/reference/count", {}, {}, epistemic_class=EpistemicClass.PERSISTED,
    provenance="reference backend: in-memory operation count", outputs=("count",),
))
register(Capability(
    "reference_submit", "Submit a synthetic example operation", "POST",
    "/reference/operations", {"record_id": FieldSpec(str, max_length=32,
                                                        pattern=r"[a-z0-9-]+")}, {},
    risk="approval_required", epistemic_class=EpistemicClass.PERSISTED,
    provenance="reference backend: synthetic operation",
))

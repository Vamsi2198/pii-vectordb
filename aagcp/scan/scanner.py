"""
Scanner — uncapped PII inventory of an existing (production) index.

Streams EVERY vector via the connector's iter_all (no cap, batched), runs the
global detector on each vector's source_text, and aggregates a full exposure
report: total PII instances, by type, by jurisdiction, which vectors are
affected, and which have no source_text (cleanable-by-re-embed vs
quarantine-only).

The count is whatever the index actually contains. Nothing is capped.
"""

from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

from ..detect.detector import PIIDetector, Finding
from ..store.connectors import VectorStoreConnector


@dataclass
class VectorExposure:
    vector_id: str
    findings: List[Finding]
    has_source: bool
    risk: float


@dataclass
class ScanReport:
    total_vectors: int = 0
    scanned_vectors: int = 0
    vectors_with_pii: int = 0
    total_pii_instances: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_jurisdiction: Dict[str, int] = field(default_factory=dict)
    cleanable: int = 0             # has source_text → re-embed
    quarantine_only: int = 0       # no source_text → can only delete
    exposures: List[VectorExposure] = field(default_factory=list)
    detector_coverage: dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "total_vectors": self.total_vectors,
            "scanned_vectors": self.scanned_vectors,
            "vectors_with_pii": self.vectors_with_pii,
            "total_pii_instances": self.total_pii_instances,
            "by_type": dict(sorted(self.by_type.items(), key=lambda x: -x[1])),
            "by_jurisdiction": dict(sorted(self.by_jurisdiction.items(), key=lambda x: -x[1])),
            "cleanable_by_reembed": self.cleanable,
            "quarantine_only_no_source": self.quarantine_only,
            "detector_coverage": self.detector_coverage,
        }


class Scanner:
    def __init__(self, detector: PIIDetector):
        self.detector = detector

    def scan(self, store: VectorStoreConnector, batch: int = 500,
             progress=None) -> ScanReport:
        rep = ScanReport(total_vectors=store.count(),
                         detector_coverage=self.detector.coverage())
        type_ctr: Counter = Counter()
        juris_ctr: Counter = Counter()

        for chunk in store.iter_all(batch=batch):
            for rec in chunk:
                rep.scanned_vectors += 1
                text = rec.source_text or ""
                if not text and rec.metadata:
                    text = rec.metadata.get("source_text") or rec.metadata.get("text") or ""
                findings = self.detector.scan(text) if text else []
                if findings:
                    rep.vectors_with_pii += 1
                    rep.total_pii_instances += len(findings)
                    for f in findings:
                        type_ctr[f.entity_type] += 1
                        juris_ctr[f.jurisdiction or "GLOBAL"] += 1
                    rep.cleanable += 1
                    rep.exposures.append(VectorExposure(
                        rec.id, findings, bool(text),
                        self.detector.risk_score(findings)))
                elif not text:
                    rep.quarantine_only += 1
            if progress:
                progress(rep.scanned_vectors, rep.total_vectors)

        rep.by_type = dict(type_ctr)
        rep.by_jurisdiction = dict(juris_ctr)
        return rep

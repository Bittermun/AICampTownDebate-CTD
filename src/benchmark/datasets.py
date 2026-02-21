"""Dataset adapter layer for benchmark runner."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
import hashlib
import json
import re

from .config_models import DatasetSpec
from .types import BenchmarkItem


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug


class OfflineFixtureAdapter:
    """Loads benchmark items from local JSONL fixtures."""

    def __init__(self, fixtures_dir: str):
        self.fixtures_dir = Path(fixtures_dir)

    def load(self, group_name: str, dataset_name: str, limit: int | None = None) -> Tuple[List[BenchmarkItem], bool]:
        """
        Returns:
        - items
        - degraded_mode flag (true for external proxy fixtures)
        """
        filename = _slugify(dataset_name) + ".jsonl"
        path = self.fixtures_dir / group_name / filename
        if not path.exists():
            raise FileNotFoundError(f"Fixture dataset not found: {path}")

        items: List[BenchmarkItem] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                items.append(
                    BenchmarkItem(
                        item_id=str(raw.get("id", f"{dataset_name}-{len(items)+1}")),
                        group=group_name,
                        dataset=dataset_name,
                        prompt=str(raw.get("prompt", "")),
                        expected=raw.get("expected"),
                        metric_values={k: float(v) for k, v in raw.get("metric_values", {}).items()},
                        tags=list(raw.get("tags", [])),
                        source_ref=str(raw.get("source_ref", "")),
                    )
                )
                if limit is not None and len(items) >= limit:
                    break

        degraded_mode = any("external_proxy" in t for item in items for t in item.tags)
        return items, degraded_mode


class HFDatasetAdapter:
    """Loads benchmark items from HuggingFace datasets with local caching."""

    def __init__(self, dataset_specs: Dict[Tuple[str, str], DatasetSpec], cache_dir: str = "benchmarks/cache"):
        self.dataset_specs = dataset_specs
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._pull_manifest: List[Dict[str, Any]] = []

    @property
    def pull_manifest(self) -> List[Dict[str, Any]]:
        return list(self._pull_manifest)

    def _cache_paths(self, group_name: str, dataset_name: str, spec: DatasetSpec) -> Tuple[Path, Path]:
        key_blob = {
            "group": group_name,
            "dataset": dataset_name,
            "hf_dataset_id": spec.hf_dataset_id,
            "hf_subset": spec.hf_subset,
            "split": spec.split,
            "column_mapping": spec.column_mapping,
        }
        raw = json.dumps(key_blob, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        base = f"{_slugify(group_name)}_{_slugify(dataset_name)}_{digest}"
        return self.cache_dir / f"{base}.jsonl", self.cache_dir / f"{base}.meta.json"

    def _resolve_split(self, requested_split: str | None, available: List[str]) -> str:
        if not available:
            raise RuntimeError("No splits available in HuggingFace dataset.")
        if requested_split and requested_split in available:
            return requested_split
        if requested_split and "_or_" in requested_split:
            for token in requested_split.split("_or_"):
                token = token.strip()
                if token in available:
                    return token
        for preferred in ("test", "validation", "train"):
            if preferred in available:
                return preferred
        return available[0]

    def _load_hf_split(self, spec: DatasetSpec):
        try:
            from datasets import get_dataset_split_names, load_dataset  # type: ignore
        except Exception as exc:
            raise RuntimeError("HuggingFace datasets package not available. Install `datasets`.") from exc
        available = list(get_dataset_split_names(spec.hf_dataset_id, spec.hf_subset))
        split = self._resolve_split(spec.split, available)
        return split, load_dataset(spec.hf_dataset_id, name=spec.hf_subset, split=split)

    def _row_to_item(
        self,
        row: Dict[str, Any],
        group_name: str,
        dataset_name: str,
        idx: int,
        spec: DatasetSpec,
        split_name: str,
    ) -> BenchmarkItem:
        mapping = spec.column_mapping or {}
        id_col = mapping.get("id", "id")
        prompt_col = mapping.get("prompt", "prompt")
        expected_col = mapping.get("expected", "expected")
        source_ref_col = mapping.get("source_ref")
        metric_map = mapping.get("metric_values", {})
        tags_field = mapping.get("tags")
        static_tags = mapping.get("static_tags", [])

        item_id = str(row.get(id_col, f"{dataset_name}-{idx+1}"))
        prompt = str(row.get(prompt_col, ""))
        expected = row.get(expected_col)
        metric_values: Dict[str, float] = {}
        if isinstance(metric_map, dict):
            for metric_name, col_name in metric_map.items():
                if col_name in row and row[col_name] is not None:
                    try:
                        metric_values[str(metric_name)] = float(row[col_name])
                    except (TypeError, ValueError):
                        continue

        tags: List[str] = []
        if isinstance(tags_field, str):
            tag_value = row.get(tags_field)
            if isinstance(tag_value, list):
                tags.extend(str(x) for x in tag_value)
            elif tag_value is not None:
                tags.append(str(tag_value))
        elif isinstance(tags_field, list):
            tags.extend(str(x) for x in tags_field)
        if isinstance(static_tags, list):
            tags.extend(str(x) for x in static_tags)

        if source_ref_col:
            source_ref = str(row.get(source_ref_col, ""))
        else:
            subset = spec.hf_subset or "_"
            source_ref = f"hf:{spec.hf_dataset_id}:{subset}:{split_name}:{idx}"

        return BenchmarkItem(
            item_id=item_id,
            group=group_name,
            dataset=dataset_name,
            prompt=prompt,
            expected=expected,
            metric_values=metric_values,
            tags=tags,
            source_ref=source_ref,
        )

    def _serialize_item(self, item: BenchmarkItem) -> Dict[str, Any]:
        return {
            "id": item.item_id,
            "prompt": item.prompt,
            "expected": item.expected,
            "metric_values": item.metric_values,
            "tags": item.tags,
            "source_ref": item.source_ref,
        }

    def _content_hash(self, rows: List[Dict[str, Any]]) -> str:
        h = hashlib.sha256()
        for row in rows:
            h.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            h.update(b"\n")
        return h.hexdigest()

    def _append_manifest(
        self,
        spec: DatasetSpec,
        split_name: str,
        row_count: int,
        content_hash: str,
        data_path: Path,
        meta_path: Path,
    ) -> None:
        self._pull_manifest.append(
            {
                "dataset_id": spec.hf_dataset_id,
                "subset": spec.hf_subset,
                "split": split_name,
                "row_count": row_count,
                "content_hash": content_hash,
                "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
                "cache_data_path": str(data_path),
                "cache_meta_path": str(meta_path),
            }
        )

    def load(self, group_name: str, dataset_name: str, limit: int | None = None) -> Tuple[List[BenchmarkItem], bool]:
        spec = self.dataset_specs.get((group_name, dataset_name))
        if spec is None:
            raise KeyError(f"No dataset spec found for {group_name}/{dataset_name}")
        if not spec.hf_dataset_id:
            raise ValueError(f"Dataset {group_name}/{dataset_name} missing hf_dataset_id")

        data_path, meta_path = self._cache_paths(group_name, dataset_name, spec)
        items: List[BenchmarkItem] = []
        serialized_rows: List[Dict[str, Any]] = []

        if data_path.exists():
            split_name = spec.split or "train"
            with data_path.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    raw = json.loads(line)
                    serialized_rows.append(raw)
                    items.append(
                        BenchmarkItem(
                            item_id=str(raw.get("id", f"{dataset_name}-{i+1}")),
                            group=group_name,
                            dataset=dataset_name,
                            prompt=str(raw.get("prompt", "")),
                            expected=raw.get("expected"),
                            metric_values={k: float(v) for k, v in raw.get("metric_values", {}).items()},
                            tags=list(raw.get("tags", [])),
                            source_ref=str(raw.get("source_ref", "")),
                        )
                    )
            if meta_path.exists():
                try:
                    meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
                    split_name = str(meta_raw.get("split", split_name))
                except Exception:
                    pass
        else:
            resolved_split, hf_rows = self._load_hf_split(spec)
            split_name = resolved_split
            for i, row in enumerate(hf_rows):
                mapped = self._row_to_item(dict(row), group_name, dataset_name, i, spec, split_name)
                items.append(mapped)
                serialized_rows.append(self._serialize_item(mapped))
            data_path.write_text(
                "\n".join(json.dumps(r, sort_keys=True) for r in serialized_rows) + ("\n" if serialized_rows else ""),
                encoding="utf-8",
            )
            meta_payload = {
                "dataset_id": spec.hf_dataset_id,
                "subset": spec.hf_subset,
                "split": resolved_split,
                "row_count": len(serialized_rows),
                "content_hash": self._content_hash(serialized_rows),
                "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

        if not serialized_rows:
            serialized_rows = [self._serialize_item(x) for x in items]
        content_hash = self._content_hash(serialized_rows)
        self._append_manifest(spec, split_name, len(items), content_hash, data_path, meta_path)

        if limit is not None and limit < len(items):
            items = items[:limit]
        return items, False

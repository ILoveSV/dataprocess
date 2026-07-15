import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path


logger = logging.getLogger('data_process')


def collect_file_info(paths):
    items = []
    for path in sorted(Path(p) for p in paths):
        if not path.exists():
            items.append({"path": str(path), "missing": True})
            continue
        stat = path.stat()
        items.append({
            "path": str(path),
            "mtime": stat.st_mtime,
            "size": stat.st_size,
        })
    return items


def build_param_signature(params):
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_cache_metadata(path):
    path = Path(path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_cache_metadata(path, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False, default=str)
    return path


def build_cache_metadata(stage, input_files, expected_outputs, params, input_dir=None, output_dir=None):
    return {
        "stage": stage,
        "created_at": datetime.now().isoformat(),
        "input_dir": str(input_dir) if input_dir is not None else None,
        "output_dir": str(output_dir) if output_dir is not None else None,
        "input_files": collect_file_info(input_files),
        "expected_outputs": collect_file_info(expected_outputs),
        "params": params,
        "param_signature": build_param_signature(params),
    }


def _paths_from_metadata(items):
    return [str(item.get("path")) for item in items or []]


def is_cache_hit(stage, input_files, expected_outputs, params, metadata_path, force=False, skip_existing=True):
    input_files = [Path(path) for path in input_files]
    expected_outputs = [Path(path) for path in expected_outputs]
    metadata_path = Path(metadata_path)

    logger.info("[cache] stage=%s", stage)
    logger.info("[cache] input_count=%s", len(input_files))
    logger.info("[cache] output_dir=%s", metadata_path.parent.parent if metadata_path.parent.name == ".cache" else metadata_path.parent)
    logger.info("[cache] force=%s", str(bool(force)).lower())
    logger.info("[cache] skip_existing=%s", str(bool(skip_existing)).lower())

    if force:
        logger.info("[cache] MISS: reason=force enabled")
        return False, "force enabled"
    if not skip_existing:
        logger.info("[cache] MISS: reason=skip-existing disabled")
        return False, "skip-existing disabled"

    if not expected_outputs:
        logger.info("[cache] MISS: reason=no expected outputs")
        return False, "no expected outputs"

    for output in expected_outputs:
        if not output.exists():
            logger.info("[cache] MISS: reason=missing output")
            return False, "missing output"

    metadata = load_cache_metadata(metadata_path)
    if metadata is None:
        logger.info("[cache] MISS: reason=missing metadata")
        return False, "missing metadata"

    current_signature = build_param_signature(params)
    if metadata.get("param_signature") != current_signature:
        logger.info("[cache] MISS: reason=parameter signature changed")
        return False, "parameter signature changed"

    current_inputs = [str(path) for path in sorted(input_files)]
    cached_inputs = sorted(_paths_from_metadata(metadata.get("input_files")))
    if cached_inputs != current_inputs:
        logger.info("[cache] MISS: reason=input file list changed")
        return False, "input file list changed"

    current_outputs = [str(path) for path in sorted(expected_outputs)]
    cached_outputs = sorted(_paths_from_metadata(metadata.get("expected_outputs")))
    if cached_outputs != current_outputs:
        logger.info("[cache] MISS: reason=output file list changed")
        return False, "output file list changed"

    newest_input = max((path.stat().st_mtime for path in input_files if path.exists()), default=0)
    oldest_output = min((path.stat().st_mtime for path in expected_outputs if path.exists()), default=0)
    if newest_input > oldest_output:
        logger.info("[cache] MISS: reason=input newer than output")
        return False, "input newer than output"

    logger.info("[cache] HIT: skip %s, outputs are up-to-date", stage)
    return True, "cache hit"

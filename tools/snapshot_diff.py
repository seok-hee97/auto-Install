"""
Phase 8: 설치 전후 파일시스템 diff — 해당 인스톨러가 생성한 파일만 정확히 추출
filesystem_monitor(실시간 watchdog)와 병행 사용 가능.

CLI:
    python tools/snapshot_diff.py snapshot --out before.json
    # (설치 실행)
    python tools/snapshot_diff.py snapshot --out after.json
    python tools/snapshot_diff.py diff --before before.json --after after.json [--out result.txt]
"""

import argparse
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

WATCH_ROOTS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
    os.path.expandvars(r"%APPDATA%"),
    os.path.expandvars(r"%LOCALAPPDATA%"),
]

# 노이즈 필터 — 이 확장자는 수집 대상에서 제외
IGNORED_EXTENSIONS = frozenset({
    '.tmp', '.log', '.etl', '.evtx', '.db-journal', '.lock',
    '.part', '.crdownload', '.download', '.~', '.bak',
})

# 노이즈 필터 — 이 경로 패턴을 포함하면 제외 (소문자 비교)
IGNORED_PATH_FRAGMENTS = (
    'windows\\temp',
    'appdata\\local\\temp',
    'appdata\\local\\microsoft\\windows',
    'appdata\\roaming\\microsoft\\windows',
    'appdata\\local\\google\\chrome',
    'appdata\\local\\microsoft\\edge',
)


# ---------------------------------------------------------------------------
# Core snapshot / diff functions
# ---------------------------------------------------------------------------

def take_snapshot(roots: list = WATCH_ROOTS) -> dict:
    """관심 경로의 파일 목록을 (size, mtime) 튜플로 스냅샷."""
    snapshot = {}
    for root in roots:
        if not os.path.exists(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fname in files:
                path = os.path.join(dirpath, fname)
                try:
                    st = os.stat(path)
                    snapshot[path] = (st.st_size, st.st_mtime)
                except OSError:
                    pass
    logger.debug("Snapshot: %d files in %d roots", len(snapshot), len(roots))
    return snapshot


def diff_snapshots(before: dict, after: dict) -> list:
    """after에만 있거나 변경된 파일 경로 목록 반환 (정렬)."""
    changed = [
        path for path, stat in after.items()
        if path not in before or before[path] != stat
    ]
    return sorted(changed)


def filter_noise(paths: list) -> list:
    """임시파일·캐시·Windows 내부 파일 제거."""
    result = []
    for path in paths:
        path_lower = path.lower()
        ext = os.path.splitext(path_lower)[1]
        if ext in IGNORED_EXTENSIONS:
            continue
        if any(frag in path_lower for frag in IGNORED_PATH_FRAGMENTS):
            continue
        result.append(path)
    return result


# ---------------------------------------------------------------------------
# Context manager — 인스톨러 실행을 감싸서 전후 diff 캡처
# ---------------------------------------------------------------------------

class InstallDiff:
    """
    설치 전후 diff를 캡처하는 컨텍스트 매니저.

    Example:
        with InstallDiff() as diff:
            gui_install(file_path)
        new_files = diff.result()
    """

    def __init__(self, roots: list = WATCH_ROOTS, apply_filter: bool = True):
        self.roots = roots
        self.apply_filter = apply_filter
        self._before: Optional[dict] = None
        self._files: list = []

    def __enter__(self) -> 'InstallDiff':
        logger.info("InstallDiff: pre-install snapshot start")
        self._before = take_snapshot(self.roots)
        logger.info("InstallDiff: pre-install snapshot done (%d files)", len(self._before))
        return self

    def __exit__(self, *_):
        logger.info("InstallDiff: post-install snapshot start")
        after = take_snapshot(self.roots)
        changed = diff_snapshots(self._before, after)
        self._files = filter_noise(changed) if self.apply_filter else changed
        logger.info("InstallDiff: %d new/modified files detected", len(self._files))

    def result(self) -> list:
        return self._files


# ---------------------------------------------------------------------------
# Snapshot serialization helpers
# ---------------------------------------------------------------------------

def save_snapshot(snapshot: dict, path: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({k: list(v) for k, v in snapshot.items()}, f, ensure_ascii=False)
    logger.info("Snapshot saved: %s (%d files)", path, len(snapshot))


def load_snapshot(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    return {k: tuple(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Install filesystem diff tool")
    sub = parser.add_subparsers(dest='cmd')

    snap = sub.add_parser('snapshot', help='Take a filesystem snapshot')
    snap.add_argument('--out', default='snapshot.json', help='Output JSON file')
    snap.add_argument('--roots', nargs='*', help='Override watch roots')

    diff = sub.add_parser('diff', help='Compare two snapshots')
    diff.add_argument('--before', default='snapshot_before.json')
    diff.add_argument('--after', default='snapshot_after.json')
    diff.add_argument('--out', default='', help='Write result to text file')
    diff.add_argument('--no-filter', action='store_true', help='Skip noise filtering')

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    if args.cmd == 'snapshot':
        roots = args.roots or WATCH_ROOTS
        snap = take_snapshot(roots)
        save_snapshot(snap, args.out)
        print(f"Snapshot saved: {args.out}  ({len(snap)} files)")

    elif args.cmd == 'diff':
        before = load_snapshot(args.before)
        after = load_snapshot(args.after)
        changed = diff_snapshots(before, after)
        if not args.no_filter:
            changed = filter_noise(changed)
        print(f"Changed / new files: {len(changed)}")
        for p in changed:
            print(f"  {p}")
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write('\n'.join(changed))
            print(f"\nResult written: {args.out}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

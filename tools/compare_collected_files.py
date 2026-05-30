"""
Phase 5: SHA-256 기반 폴더 비교 + PE 파일 매칭률 계산 + installer type 성공률 리포트

Usage:
    python tools/compare_collected_files.py compare <folder_a> <folder_b> [--csv out.csv]
    python tools/compare_collected_files.py report  <install_summary.csv>
"""

import argparse
import csv
import hashlib
import os
import sys
from collections import defaultdict


# ---------------------------------------------------------------------------
# SHA-256 / PE helpers
# ---------------------------------------------------------------------------

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
    except OSError:
        return ''
    return h.hexdigest()


def is_pe_file(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            return f.read(2) == b'MZ'
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Folder collection
# ---------------------------------------------------------------------------

def collect_files(folder: str) -> dict:
    """Returns {rel_path: {'abs': abs_path, 'sha256': digest, 'pe': bool}}."""
    result = {}
    for root, _, files in os.walk(folder):
        for fname in files:
            abs_path = os.path.join(root, fname)
            rel = os.path.relpath(abs_path, folder)
            digest = sha256_file(abs_path)
            if digest:
                result[rel] = {
                    'abs': abs_path,
                    'sha256': digest,
                    'pe': is_pe_file(abs_path),
                }
    return result


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_folders(folder_a: str, folder_b: str) -> dict:
    """Compare folder_b against folder_a by SHA-256 hash."""
    files_a = collect_files(folder_a)
    files_b = collect_files(folder_b)

    hashes_a = {info['sha256'] for info in files_a.values()}

    matched, matched_pe, only_b = [], [], []

    for rel, info in files_b.items():
        if info['sha256'] in hashes_a:
            matched.append(rel)
            if info['pe']:
                matched_pe.append(rel)
        else:
            only_b.append(rel)

    only_a = [
        rel for rel, info in files_a.items()
        if info['sha256'] not in {i['sha256'] for i in files_b.values()}
    ]

    total_b = len(files_b)
    pe_b = sum(1 for i in files_b.values() if i['pe'])

    return {
        'total_a': len(files_a),
        'total_b': total_b,
        'matched': len(matched),
        'match_percent': round(len(matched) / total_b * 100, 1) if total_b else 0.0,
        'pe_files_b': pe_b,
        'matched_pe': len(matched_pe),
        'match_pe_percent': round(len(matched_pe) / pe_b * 100, 1) if pe_b else 0.0,
        'only_in_a': only_a,
        'only_in_b': only_b,
        'matched_files': matched,
        'matched_pe_files': matched_pe,
        'files_b': files_b,
    }


def print_compare_result(result: dict, folder_a: str, folder_b: str) -> None:
    print(f"\nFolder A : {folder_a}  ({result['total_a']} files)")
    print(f"Folder B : {folder_b}  ({result['total_b']} files)")
    print(f"Matched  : {result['matched']:>5} / {result['total_b']}  ({result['match_percent']}%)")
    print(f"PE match : {result['matched_pe']:>5} / {result['pe_files_b']}  ({result['match_pe_percent']}%)")

    if result['only_in_b']:
        print(f"\nOnly in B ({len(result['only_in_b'])}):")
        for p in result['only_in_b'][:30]:
            print(f"  {p}")
        if len(result['only_in_b']) > 30:
            print(f"  ... ({len(result['only_in_b']) - 30} more)")


def write_compare_csv(result: dict, out_path: str) -> None:
    pe_set = set(result['matched_pe_files'])
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['path', 'sha256', 'status', 'is_pe'])
        for rel in result['matched_files']:
            info = result['files_b'].get(rel, {})
            w.writerow([rel, info.get('sha256', ''), 'matched', rel in pe_set])
        for rel in result['only_in_b']:
            info = result['files_b'].get(rel, {})
            w.writerow([rel, info.get('sha256', ''), 'only_in_b', info.get('pe', '')])
    print(f"\nCSV written: {out_path}")


# ---------------------------------------------------------------------------
# install_summary.csv report  (Phase 5.3)
# ---------------------------------------------------------------------------

def summarize_report(report_csv: str) -> None:
    if not os.path.exists(report_csv):
        print(f"Report not found: {report_csv}")
        sys.exit(1)

    stats = defaultdict(lambda: {
        'total': 0, 'zip': 0, 'silent': 0, 'gui': 0,
        'classify_failed': 0, 'zip_failed': 0, 'silent_failed': 0, 'gui_failed': 0,
        'elapsed_sum': 0.0,
    })

    with open(report_csv, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t = row.get('installer_type', 'Unknown') or 'Unknown'
            stage = row.get('stage', '')
            result = row.get('result', '')
            elapsed = float(row.get('elapsed_sec', 0) or 0)
            stats[t]['total'] += 1
            stats[t]['elapsed_sum'] += elapsed
            key = f"{stage}_failed" if result == 'failed' else stage
            if key in stats[t]:
                stats[t][key] += 1

    col = f"{'Type':<32} {'Total':>6} {'Zip':>5} {'Silent':>7} {'GUI':>5} {'Failed':>7} {'Rate':>6} {'Avg(s)':>7}"
    print(f"\n{col}")
    print('-' * 80)

    grand = defaultdict(float)
    for t, s in sorted(stats.items()):
        success = s['zip'] + s['silent'] + s['gui']
        rate = round(success / s['total'] * 100, 1) if s['total'] else 0.0
        avg_elapsed = round(s['elapsed_sum'] / s['total'], 1) if s['total'] else 0.0
        failed = s['gui_failed']
        print(f"{t:<32} {s['total']:>6} {s['zip']:>5} {s['silent']:>7} {s['gui']:>5} "
              f"{failed:>7} {rate:>5}% {avg_elapsed:>7}")
        for k, v in s.items():
            grand[k] += v

    total = int(grand['total'])
    total_success = int(grand['zip'] + grand['silent'] + grand['gui'])
    total_rate = round(total_success / total * 100, 1) if total else 0.0
    avg = round(grand['elapsed_sum'] / total, 1) if total else 0.0
    print('-' * 80)
    print(f"{'TOTAL':<32} {total:>6} {int(grand['zip']):>5} {int(grand['silent']):>7} "
          f"{int(grand['gui']):>5} {int(grand['gui_failed']):>7} {total_rate:>5}% {avg:>7}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Collected file comparison and install success rate reporter"
    )
    sub = parser.add_subparsers(dest='cmd')

    cmp = sub.add_parser('compare', help='Compare two folders by SHA-256 hash')
    cmp.add_argument('folder_a', help='Reference folder')
    cmp.add_argument('folder_b', help='Collected folder to verify')
    cmp.add_argument('--csv', default='', help='Write results to CSV')

    rep = sub.add_parser('report', help='Summarize install_summary.csv by installer type')
    rep.add_argument('csv', help='Path to install_summary.csv')

    args = parser.parse_args()

    if args.cmd == 'compare':
        result = compare_folders(args.folder_a, args.folder_b)
        print_compare_result(result, args.folder_a, args.folder_b)
        if args.csv:
            write_compare_csv(result, args.csv)

    elif args.cmd == 'report':
        summarize_report(args.csv)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()

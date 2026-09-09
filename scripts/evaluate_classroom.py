"""Offline classroom evaluation. No paid call without --paid."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['check', 'replay', 'generate'], default='check')
    parser.add_argument('--paid', action='store_true')
    parser.add_argument('--judge-max-usd', type=float)
    parser.add_argument('--generator-max-usd', type=float)
    parser.add_argument('--input', type=Path, help='versioned synthetic/anonymized replay JSON')
    parser.add_argument('--baseline', type=Path, help='previous results.json')
    parser.add_argument('--cases', nargs='+', help='e.g. F07 F08 F31')
    args = parser.parse_args()
    if args.input and args.mode != 'replay':
        parser.error('--input 仅用于 replay')
    # Default runs have an actual network fence, not just missing API keys.
    os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
    os.environ['DEEPEVAL_UPDATE_WARNING_OPT_IN'] = '0'
    if not args.paid:
        import socket
        from evals.offline_guard import blocked
        socket.socket.connect = socket.socket.connect_ex = blocked
        socket.create_connection = socket.getaddrinfo = blocked
    from evals.runner import run
    try:
        result = run(args.mode, paid=args.paid, judge_limit=args.judge_max_usd,
                     generator_limit=args.generator_max_usd, input_path=args.input,
                     baseline=args.baseline, case_ids=args.cases)
    except (ValueError, TypeError, OSError) as exc:
        print('评测未完成：' + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print('评测启动或执行异常：' + type(exc).__name__ + '；请检查依赖和测试账本配置', file=sys.stderr)
        return 2
    print(ROOT / 'artifacts/private/classroom-eval' / result['run_id'] / 'summary.md')
    print(result['summary'])
    if args.mode == 'check':
        return int(any(r['status'] in ('fail', 'error') for r in result['results'] if r['stage'] == 'code'))
    return 2 if result['summary']['error'] else 0  # Semantic failures are advisory, not a release gate.


if __name__ == '__main__':
    raise SystemExit(main())

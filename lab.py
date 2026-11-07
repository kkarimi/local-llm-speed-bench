"""Benchmark running models and generate an offline leaderboard."""
import argparse
import json
from pathlib import Path

from engine import discover, measure, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action',required=True)
    bench = actions.add_parser('bench',help='Measure a running streaming chat endpoint')
    bench.add_argument('--model',required=True)
    bench.add_argument('--runtime',required=True)
    bench.add_argument('--url',default='http://127.0.0.1:8080/v1')
    bench.add_argument('--samples',type=int,default=3)
    bench.add_argument('--tokens',type=int,default=256)
    bench.add_argument('--seed',default='league-1')
    bench.add_argument('--progress',action='store_true',help='Print progress before each request')
    workloads = bench.add_mutually_exclusive_group()
    workloads.add_argument('--include-8k',action='store_true')
    workloads.add_argument('--cases',choices=['short','long','8k'],nargs='+')
    models = actions.add_parser('models', help='List endpoint model IDs as JSON')
    models.add_argument('--url', default='http://127.0.0.1:8080/v1')
    bench.add_argument('--out',type=Path,required=True)
    board = actions.add_parser('report',help='Generate a standalone HTML report')
    board.add_argument('runs',type=Path,nargs='+')
    board.add_argument('--machine',default='Local inference measurements')
    board.add_argument('--out',type=Path,default=Path('league.html'))
    args = parser.parse_args()
    try:
        if args.action == 'models':
            print(json.dumps(discover(args.url)))
            return
        if args.action == 'bench':
            progress = (lambda message: print(message, flush=True)) if args.progress else None
            measure(args, progress)
        else:
            report(args)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1,f'Error: {exc}\n')
    print(args.out)


if __name__ == '__main__':
    main()

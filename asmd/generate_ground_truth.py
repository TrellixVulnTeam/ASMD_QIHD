from .conversion_tool import create_gt
from . import alignment_stats
import os
import sys
import argparse
print("Usage: ")
print("  python3 generate_ground_truth.py [list of datasets to be excluded]")
print()

THISDIR = os.path.dirname(os.path.realpath(__file__))

argparser = argparse.ArgumentParser(
    description='Generate ASMD ground-truth from other sources')

argparser.add_argument(
    '--misalign',
    action='store_true',
    help="Generate ground-truth, compute alignment stats, regenerate groundtruth with artificial misalignment")

args = argparser.parse_args()

create_gt(os.path.join(THISDIR, 'datasets.json'), sys.argv, gztar=True,
          alignment_stats=None)

if args.misalign:
    stats = alignment_stats.main()
    create_gt(os.path.join(THISDIR, 'datasets.json'), sys.argv, gztar=True,
              alignment_stats=stats)
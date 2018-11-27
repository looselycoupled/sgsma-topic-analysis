#!/usr/bin/env python3
# summarize
# Summarizes the status of the database and error output by wrangle.
#
# Author:  Benjamin Bengfort <benjamin@bengfort.com>
# Created: Tue Nov 27 10:24:14 2018 -0500
#
# ID: summarize.py [] benjamin@bengfort.com $

"""
Summarizes the status of the database and error output by wrangle.
"""

##########################################################################
## Imports
##########################################################################

import os
import json
import sqlite3
import argparse

from tabulate import tabulate
from functools import partial
from collections import Counter

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
ERRS = os.path.join(DATA, "wrangle_report.json")
DBPATH = os.path.join(DATA, "biblio.db")

tabulate = partial(tabulate, headers='firstrow', tablefmt='pipe')


def summarize(db=DBPATH, errs=ERRS):
    table_counts(db)
    error_report(errs)

def table_counts(db=DBPATH):
    """
    Prints the table counts for all tables in the database
    """
    conn = sqlite3.connect(db)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    tables.sort()

    counts = [['Table', 'Rows']]
    for table in tables:
        cursor.execute("SELECT count(*) FROM {}".format(table))
        count = cursor.fetchone()[0]
        counts.append([table, count])

    print(tabulate(counts))
    print("\n")


def error_report(errs=ERRS):
    errors = []
    with open(errs, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                errors.append(json.loads(line))

    err_types = Counter([err['error'] for err in errors])
    err_types_table = [["Error", "Count"]] + list(err_types.most_common())
    err_types_table += [["Total", sum(err_types.values())]]
    print(tabulate(err_types_table))

    # TODO: summarize details about errors

    print("\n")


if __name__ == '__main__':
    # CLI Command
    parser = argparse.ArgumentParser(
        description="parse the output of the wrangle command"
    )

    # Argument definition
    args = {
        ('-r', '--report'): {
            'type': str, 'metavar': 'PATH', 'default': ERRS,
            'help': 'location of the error report output from wrangle.py',
        },
        ('-d', '--db'): {
            'type': str, 'metavar': 'PATH', 'default': DBPATH,
            'help': 'location of sqlite database',
        },
    }

    # Add arguments to the parser
    for pargs, kwargs in args.items():
        if isinstance(pargs, str):
            pargs = (pargs,)
        parser.add_argument(*pargs, **kwargs)

    # Parsed arguments
    args = parser.parse_args()

    # Wrangle the database
    # try:
    summarize(db=args.db, errs=args.report)
    # except Exception as e:
    #     parser.error(str(e))

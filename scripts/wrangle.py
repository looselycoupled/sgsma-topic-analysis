#!/usr/bin/env python3
# wrangle
# Convert the CSV files into a SQLite database.
#
# Author:  Benjamin Bengfort <benjamin@pingthings.io>
# Created: Mon Nov 26 11:22:04 2018 -0500
#
# ID: wrangle.py [] benjamin@bengfort.com $

"""
Convert the CSV files into a SQLite database.
"""

##########################################################################
## Imports
##########################################################################

import os
import csv
import json
import sqlite3
import argparse

from collections import Counter

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
DOCS = os.path.join(DATA, "lit-review-doc-metadata.csv")
CATS = os.path.join(DATA, "lit-review-categories.csv")
DBPATH = os.path.join(DATA, "biblio.db")
SCHEMA = os.path.join(BASE, "scripts", "schema.sql")


def wrangle(docs=DOCS, cats=CATS, path=DBPATH, force=False):
    """
    Wrangle the CSV documents into a database structure.
    """
    # Create the database from the specified schema.
    makedb(path, force)

    # Connect to the database
    conn = sqlite3.connect(path)

    # Load the documents from the CSV file
    with open(docs, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            err = parse_doc_row(row, conn)
            if err is not None:
                print(err)

    # Load the categories from the CSV file
    with open(cats, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            err = parse_cat_row(row, conn)
            if err is not None:
                print(err)

    conn.commit()
    conn.close()


def makedb(path, force=False):
    """
    Creates an empty database with the given schema; if force is true -
    deletes any existing database, otherwise raises an exception.
    """

    # Check if database already exists
    if os.path.exists(path):
        if force:
            os.remove(path)
        else:
            raise ValueError("database already exists at {}".format(path))

    # Connect to the database
    conn = sqlite3.connect(path)

    # Load and execute SQL file
    with open(SCHEMA, 'r') as f:
        sql = f.read()
        cursor = conn.cursor()
        cursor.executescript(sql)

    conn.commit()
    conn.close()


def parse_doc_row(row, conn):
    """
    Insert a row for each document
    """
    cursor = conn.cursor()

    publication_id = get_or_create_publication(row, cursor)

    try:
        article_id = insert_article(row, publication_id, cursor)
    except Exception as e:
        error = {
            "error": "could not insert article",
            "exception": str(e),
            "data": {
                "title": row["Document Title"],
                "pub_year": row["Publication_Year"],
            }
        }

        return json.dumps(error)

    errors = []
    errs = handle_authors(row, article_id, cursor)
    if errs is not None:
        errors.append(errs)

    errs = handle_keywords(row, article_id, cursor)
    if errs is not None:
        errors.append(errs)

    if errors:
        return "\n".join(errors)
    return None


def parse_cat_row(row, conn):
    """
    Insert a row for each category
    """
    cursor = conn.cursor()

    article_id = lookup_article(row["Document Title"].strip(), row["\ufeffPublication_Year"], cursor)
    if article_id is None:
        error = {
            "error": "could not lookup article for label",
            "data": {
                "title": row["Document Title"],
                "pub_year": row["\ufeffPublication_Year"],
                "label": row["Domain"],
            }
        }
        return json.dumps(error)

    label_id = get_or_create_label(row["Domain"].strip(), "sgsma_manual", cursor)

    try:
        insert_article_labels(label_id, article_id, cursor)
    except Exception as e:
        error = {
            "error": "could not assign label to article",
            "exception": str(e),
            "data": {
                "title": row["Document Title"],
                "pub_year": row["\ufeffPublication_Year"],
                "label": row["Domain"],
                "article_id": article_id,
                "label_id": label_id,
            }
        }
        return json.dumps(error)

    return None


def handle_authors(row, article_id, cursor):
    authors = [a.strip() for a in row["Authors"].split(";")]
    affiliations = [a.strip() for a in row["Author Affiliations"].split(";")]

    # Check for duplicate authors?
    counts = Counter(authors)
    dups = [a for a,c in counts.items() if c>1]
    if dups:
        for dup in dups:
            j = 0
            for i, elem in enumerate(authors):
                if elem == dup:
                    j += 1
                    if j > 1:
                        authors[i] = "{} ({})".format(elem, j)

    for author, affiliation in zip(authors, affiliations):
        affiliation_id = get_or_create_affiliation(affiliation, cursor)
        author_id = get_or_create_author(author, cursor)
        insert_author_affiliation(author_id, affiliation_id, cursor)
        insert_article_author(author_id, article_id, cursor)

    if dups:
        error = {
            "error": "non-unique author names for article",
            "data": {
                "title": row["Document Title"],
                "pub_year": row["Publication_Year"],
                "article_id": article_id,
                "duplicates": dups,
            }
        }
        return json.dumps(error)

    return None


def handle_keywords(row, article_id, cursor):
    term_types = {
        "Author Keywords": "author",
        "IEEE Terms": "ieee",
        "INSPEC Controlled Terms": "inspec_controlled",
        "INSPEC Non-Controlled Terms": "inspec_non_controlled",
        "Mesh_Terms": "mesh",
    }

    errs = []

    for kws, kwt in term_types.items():
        keywords = Counter([k.strip() for k in row[kws].split(";")])
        for kw, count in keywords.items():
            if count > 1:
                error = {
                    "error": "duplicate keywords",
                    "data": {
                        "title": row["Document Title"],
                        "pub_year": row["Publication_Year"],
                        "article_id": article_id,
                        "term": kw,
                        "term_type": kwt,
                        "count": count,
                    }
                }
                errs.append(error)

            kwid = get_or_create_keyword(kw, kwt, cursor)
            if kwid is not None:
                insert_article_keywords(kwid, article_id, cursor)

    if errs:
        return "\n".join([json.dumps(error) for error in errs])
    return None


def lookup_article(title, year, cursor):
    year = pint(year, default=None)
    sql = "SELECT id FROM articles WHERE title=?"
    cursor.execute(sql, (title,))

    item = cursor.fetchone()
    if item is not None:
        item = item[0]
    return item


def get_or_create_publication(row, cursor):
    """
    Get or create a publication
    """
    title = row["Publication Title"].strip()
    sql = "SELECT id FROM publications WHERE title=?"
    cursor.execute(sql, (title,))

    pub = cursor.fetchone()
    if pub is None:
        sql = "INSERT INTO publications (title, publisher, meeting_date) VALUES (?,?,?)"
        meeting_date, publisher = row["Meeting Date"].strip(), row["Publisher"].strip()
        cursor.execute(sql, (title, publisher, meeting_date))
        pub = cursor.lastrowid
    else:
        pub = pub[0]

    return pub


def insert_article(row, publication_id, cursor):
    """
    Insert an article into the database
    """
    fields = {
        'title': row["Document Title"].strip(),
        'abstract': row["Abstract"].strip(),
        'xplore_date': row["Date Added To Xplore"].strip(),
        'pub_year': pint(row["Publication_Year"], None),
        'volume': pint(row["Volume"], None),
        'issue': row["Issue"].strip(),
        'start_page': pint(row["Start Page"], None),
        'end_page': pint(row["End Page"], None),
        'issn': row["ISSN"].strip(),
        'isbn': row["ISBNs"].strip(),
        'doi': row["DOI"].strip(),
        'funding_info': row["Funding Information"].strip(),
        'pdf_link': row["PDF Link"].strip(),
        'citation_count': pint(row["Article Citation Count"], None),
        'reference_count': pint(row["Reference Count"], None),
        'copyright_year': pint(row["Copyright Year"], None),
        'license': row["License"].strip(),
        'online_date': row["Online Date"].strip(),
        'document_identifier': row["Document Identifier"].strip(),
        'publication_id': publication_id,
    }
    fields = dict(filter(lambda x: x[1] is not None, fields.items()))

    sql = "INSERT INTO articles ({}) VALUES ({})".format(",".join(fields.keys()), ",".join(["?"]*len(fields)))
    cursor.execute(sql, tuple(fields.values()))
    return cursor.lastrowid


def get_or_create_affiliation(affiliation, cursor):
    sql = "SELECT id FROM affiliations WHERE name=?"
    cursor.execute(sql, (affiliation,))

    item = cursor.fetchone()
    if item is None:
        sql = "INSERT INTO affiliations (name) VALUES (?)"
        cursor.execute(sql, (affiliation,))
        item = cursor.lastrowid
    else:
        item = item[0]

    return item


def get_or_create_author(author, cursor):
    sql = "SELECT id FROM authors WHERE name=?"
    cursor.execute(sql, (author,))

    item = cursor.fetchone()
    if item is None:
        sql = "INSERT INTO authors (name) VALUES (?)"
        cursor.execute(sql, (author,))
        item = cursor.lastrowid
    else:
        item = item[0]

    return item


def get_or_create_keyword(term, term_type, cursor):
    term = term.strip()
    term_type = term_type.strip()
    if not term or not term_type:
        return None

    sql = "SELECT id FROM keywords WHERE term=? AND type=?"
    cursor.execute(sql, (term,term_type))

    item = cursor.fetchone()
    if item is None:
        sql = "INSERT INTO keywords (term, type) VALUES (?,?)"
        cursor.execute(sql, (term,term_type))
        item = cursor.lastrowid
    else:
        item = item[0]

    return item


def get_or_create_label(label, label_type, cursor):
    label = label.strip()
    label_type = label_type.strip()
    if not label or not label_type:
        return None

    sql = "SELECT id FROM labels WHERE name=? AND type=?"
    cursor.execute(sql, (label,label_type))

    item = cursor.fetchone()
    if item is None:
        sql = "INSERT INTO labels (name, type) VALUES (?,?)"
        cursor.execute(sql, (label,label_type))
        item = cursor.lastrowid
    else:
        item = item[0]

    return item


def insert_author_affiliation(author_id, affiliation_id, cursor):
    sql = "INSERT INTO author_affiliations (author_id, affiliation_id) VALUES (?,?)"
    try:
        cursor.execute(sql, (author_id, affiliation_id))
    except sqlite3.IntegrityError:
        return None
    return cursor.lastrowid


def insert_article_author(author_id, article_id, cursor):
    sql = "INSERT INTO author_articles (author_id, article_id) VALUES (?,?)"
    cursor.execute(sql, (author_id, article_id))
    return cursor.lastrowid


def insert_article_keywords(keyword_id, article_id, cursor):
    sql = "INSERT INTO article_keywords (keyword_id, article_id) VALUES (?,?)"
    cursor.execute(sql, (keyword_id, article_id))
    return cursor.lastrowid


def insert_article_labels(label_id, article_id, cursor):
    sql = "INSERT INTO article_labels (label_id, article_id) VALUES (?,?)"
    cursor.execute(sql, (label_id, article_id))
    return cursor.lastrowid


def pint(n, default=0):
    """
    Parse integer or return the default value
    """
    try:
        return int(n.strip())
    except ValueError:
        return default


if __name__ == '__main__':
    # CLI Command
    parser = argparse.ArgumentParser(
        description="convert CSV files into SQLite database"
    )

    # Argument definition
    args = {
        ('-d', '--docs'): {
            'type': str, 'metavar': 'PATH', 'default': DOCS,
            'help': 'location of document metadata CSV file',
        },
        ('-c', '--cats'): {
            'type': str, 'metavar': 'PATH', 'default': CATS,
            'help': 'location of taxonomic categories CSV file',
        },
        ('-o', '--out'): {
            'type': str, 'metavar': 'PATH', 'default': DBPATH,
            'help': 'location to save the sqlite3 database to',
        },
        ('-f', '--force'): {
            'action': 'store_true', 'default': False,
            'help': 'delete existing database and rebuild',
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
    try:
        wrangle(docs=args.docs, cats=args.cats, path=args.out, force=args.force)
    except Exception as e:
        parser.error(str(e))

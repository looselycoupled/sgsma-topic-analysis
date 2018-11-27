-- Schema for the biblio database (SQLite3)

CREATE TABLE publications (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL UNIQUE,
    publisher TEXT,
    meeting_date TEXT
);

CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    xplore_date TEXT,
    pub_year INTEGER,
    volume INTEGER,
    issue TEXT,
    start_page INTEGER,
    end_page INTEGER,
    issn TEXT,
    isbn TEXT,
    doi TEXT,
    funding_info TEXT,
    pdf_link TEXT,
    citation_count INTEGER,
    reference_count INTEGER,
    copyright_year INTEGER,
    license TEXT,
    online_date TEXT,
    document_identifier TEXT,
    publication_id INTEGER,
    FOREIGN KEY (publication_id) REFERENCES publications (id) ON DELETE SET NULL,
    UNIQUE(title, pub_year)
);

CREATE TABLE authors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE affiliations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE author_affiliations (
    author_id INTEGER NOT NULL,
    affiliation_id INTEGER NOT NULL,
    PRIMARY KEY (author_id, affiliation_id),
    FOREIGN KEY (author_id) REFERENCES authors (id) ON DELETE CASCADE,
    FOREIGN KEY (affiliation_id) REFERENCES affiliations (id) ON DELETE RESTRICT
);

CREATE TABLE author_articles (
    author_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    PRIMARY KEY (author_id, article_id),
    FOREIGN KEY (author_id) REFERENCES authors (id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE
);

CREATE TABLE labels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    UNIQUE (name, type)
);

-- Keywords specified by type (e.g. author, IEEE, INSPEC controlled, INSPEC non-controlled, mesh)
CREATE TABLE keywords (
    id INTEGER PRIMARY KEY,
    term TEXT NOT NULL,
    type TEXT NOT NULL,
    UNIQUE (term, type)
);

CREATE TABLE article_labels (
    label_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    PRIMARY KEY (label_id, article_id),
    FOREIGN KEY (label_id) REFERENCES labels (id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE
);

CREATE TABLE article_keywords (
    keyword_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    PRIMARY KEY (keyword_id, article_id),
    FOREIGN KEY (keyword_id) REFERENCES keywords (id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles (id) ON DELETE CASCADE
);

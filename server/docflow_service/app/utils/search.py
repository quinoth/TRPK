from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID, NUMERIC
from whoosh.qparser import QueryParser
import os

# Создаём схему индекса
schema = Schema(
    id=NUMERIC(stored=True),
    title=TEXT,
    content=TEXT,
    category=TEXT,
    tags=TEXT
)

if not os.path.exists("indexdir"):
    os.mkdir("indexdir")
    ix = create_in("indexdir", schema)
else:
    ix = open_dir("indexdir")

def add_to_index(doc):
    writer = ix.writer()
    writer.update_document(
        id=doc.id,
        title=doc.title,
        content=doc.content,
        category=doc.category,
        tags=" ".join(doc.tags)
    )
    writer.commit()

def search_documents(query_str: str, limit=10):
    with ix.searcher() as searcher:
        query = QueryParser("content", ix.schema).parse(query_str)
        results = searcher.search(query, limit=limit)
        return [r["id"] for r in results]
"""Retrieval-augmented generation: the knowledge base the assistant explains terms from.

Articles in `knowledge/*.md` are split into passages (one per section, longer sections by
paragraph), each passage is embedded with Gemini's embedding model into a 768-number vector,
and the vectors are stored in PostgreSQL (pgvector). A question is embedded the same way and
the passages with the highest cosine similarity are given to the model as tool results, so its
explanations come from vetted text rather than from memory.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.chatbot.llm import LLM
from app.models.chat import KbChunk, KbDocument

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
SOURCE = "GoalWise knowledge base (written for this project from general investor education)"
MAX_CHUNK_CHARS = 1200
TOP_K = 4


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    sections: list[tuple[str, str]]  # (heading, text)

    @property
    def text(self) -> str:
        return "\n\n".join(f"{h}\n{t}" for h, t in self.sections)


@dataclass(frozen=True)
class Passage:
    slug: str
    title: str
    heading: str
    content: str
    similarity: float  # cosine similarity, 1 = same direction


def parse(path: Path) -> Article:
    """ "# Title", then "## Heading" sections of paragraphs."""
    lines = path.read_text(encoding="utf-8").splitlines()
    title = lines[0].removeprefix("# ").strip()
    sections: list[tuple[str, list[str]]] = []
    for line in lines[1:]:
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
    return Article(path.stem, title, [(h, "\n".join(body).strip()) for h, body in sections if body])


def chunks(article: Article) -> list[tuple[str, str]]:
    """(heading, passage) pairs, each at most about MAX_CHUNK_CHARS long."""
    out: list[tuple[str, str]] = []
    for heading, text in article.sections:
        current = ""
        for paragraph in re.split(r"\n\s*\n", text):
            if current and len(current) + len(paragraph) > MAX_CHUNK_CHARS:
                out.append((heading, current))
                current = paragraph
            else:
                current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            out.append((heading, current))
    return out


def _embedding_text(title: str, heading: str, content: str) -> str:
    # The title and heading give a passage its context ("Debt funds - Credit risk").
    return f"{title} - {heading}\n{content}"


def load_articles(directory: Path = KNOWLEDGE_DIR) -> list[Article]:
    return [parse(p) for p in sorted(directory.glob("*.md"))]


@dataclass(frozen=True)
class IngestReport:
    added: int
    updated: int
    unchanged: int
    removed: int
    chunks: int


def ingest(db: Session, llm: LLM, articles: list[Article] | None = None) -> IngestReport:
    """Embed new or changed articles and drop deleted ones. Safe to run again (idempotent)."""
    articles = load_articles() if articles is None else articles
    existing = {d.slug: d for d in db.scalars(select(KbDocument))}
    added = updated = unchanged = total = 0
    for article in articles:
        digest = hashlib.sha256(f"{article.title}\n{article.text}".encode()).hexdigest()
        document = existing.get(article.slug)
        if (
            document is not None
            and document.content_hash == digest
            and document.embedding_model == llm.embedding_model
        ):
            unchanged += 1
            total += len(document.chunks)
            continue
        pieces = chunks(article)
        vectors = llm.embed([_embedding_text(article.title, h, c) for h, c in pieces], "document")
        if document is None:
            document = KbDocument(slug=article.slug)
            db.add(document)
            added += 1
        else:
            document.chunks.clear()
            db.flush()
            updated += 1
        document.title = article.title
        document.source = SOURCE
        document.content_hash = digest
        document.embedding_model = llm.embedding_model
        document.chunks = [
            KbChunk(chunk_index=i, heading=h, content=c, embedding=v)
            for i, ((h, c), v) in enumerate(zip(pieces, vectors, strict=True))
        ]
        total += len(pieces)
    gone = set(existing) - {a.slug for a in articles}
    if gone:
        db.execute(delete(KbDocument).where(KbDocument.slug.in_(gone)))
    db.commit()
    return IngestReport(added, updated, unchanged, len(gone), total)


def is_empty(db: Session) -> bool:
    return db.scalar(select(KbChunk.id).limit(1)) is None


def search(db: Session, llm: LLM, question: str, k: int = TOP_K) -> list[Passage]:
    """The k passages closest to the question (cosine distance, the <=> operator)."""
    vector = llm.embed([question], "query")[0]
    distance = KbChunk.embedding.cosine_distance(vector)
    rows = db.execute(
        select(KbChunk, KbDocument, distance.label("distance"))
        .join(KbDocument, KbDocument.id == KbChunk.document_id)
        .order_by(distance)
        .limit(k)
    ).all()
    return [
        Passage(doc.slug, doc.title, chunk.heading, chunk.content, round(1 - float(dist), 4))
        for chunk, doc, dist in rows
    ]

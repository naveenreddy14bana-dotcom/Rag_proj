import csv
import math
import os
import re
from collections import Counter
from pathlib import Path

from django.conf import settings

from .models import Document


WORD_RE = re.compile(r"[A-Za-z0-9_]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


class UnsupportedDocumentError(Exception):
    pass


def extract_document_text(document):
    path = Path(document.file.path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".csv":
        return _extract_csv_text(path)
    if suffix in {".docx", ".doc"}:
        return _extract_docx_text(path)

    raise UnsupportedDocumentError(f"{suffix or 'This file type'} is not supported.")


def answer_question(question):
    documents = list(Document.objects.all().order_by("-uploaded_at"))
    if not documents:
        return {
            "answer": "Please upload a document first, then ask your question.",
            "sources": [],
        }

    chunks = []
    errors = []

    for document in documents:
        try:
            text = extract_document_text(document)
        except Exception as exc:
            errors.append(f"{document.title}: {exc}")
            continue

        for index, chunk in enumerate(_chunk_text(text)):
            chunks.append(
                {
                    "document_id": document.id,
                    "title": document.title,
                    "chunk_index": index,
                    "text": chunk,
                }
            )

    if not chunks:
        detail = " ".join(errors) if errors else "No readable text was found."
        return {
            "answer": f"I could not read text from the uploaded document(s). {detail}",
            "sources": [],
        }

    matches = _rank_chunks(question, chunks)[:4]
    if not matches:
        return {
            "answer": "I could not find that information in the uploaded document(s).",
            "sources": [],
        }

    llm_answer = _answer_with_groq(question, matches)
    answer = llm_answer or _answer_from_matches(question, matches)

    return {
        "answer": answer,
        "sources": [
            {
                "document_id": match["document_id"],
                "title": match["title"],
                "chunk": match["chunk_index"] + 1,
            }
            for match in matches
        ],
    }


def _extract_pdf_text(path):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n".join(pages)


def _extract_docx_text(path):
    from docx import Document as DocxDocument

    doc = DocxDocument(str(path))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs)


def _extract_csv_text(path):
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            rows.append(" | ".join(cell.strip() for cell in row if cell.strip()))

    return "\n".join(rows)


def _chunk_text(text, size=900, overlap=160):
    clean_text = re.sub(r"\s+", " ", text).strip()
    if not clean_text:
        return []

    chunks = []
    start = 0

    while start < len(clean_text):
        end = min(start + size, len(clean_text))
        chunks.append(clean_text[start:end].strip())
        if end == len(clean_text):
            break
        start = max(0, end - overlap)

    return chunks


def _rank_chunks(question, chunks):
    question_terms = _term_counts(question)
    if not question_terms:
        return []

    scored = []
    total_chunks = len(chunks)
    document_frequency = Counter()
    chunk_terms = []

    for chunk in chunks:
        terms = _term_counts(chunk["text"])
        chunk_terms.append(terms)
        document_frequency.update(terms.keys())

    for chunk, terms in zip(chunks, chunk_terms):
        score = 0.0
        for term, question_count in question_terms.items():
            if term not in terms:
                continue
            inverse_document_frequency = math.log((1 + total_chunks) / (1 + document_frequency[term])) + 1
            score += question_count * terms[term] * inverse_document_frequency

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored]


def _term_counts(text):
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
        "is", "it", "of", "on", "or", "that", "the", "this", "to", "was",
        "what", "when", "where", "which", "who", "why", "with", "you", "your",
    }
    terms = [term.lower() for term in WORD_RE.findall(text)]
    return Counter(term for term in terms if len(term) > 2 and term not in stop_words)


def _answer_with_groq(question, matches):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return ""

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        context = "\n\n".join(
            f"Source: {match['title']} chunk {match['chunk_index'] + 1}\n{match['text']}"
            for match in matches
        )
        model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer only from the provided document context. "
                        "If the answer is not in the context, say you cannot find it."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {question}",
                },
            ],
            temperature=0.1,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


def _answer_from_matches(question, matches):
    question_terms = set(_term_counts(question).keys())
    sentences = []

    for match in matches:
        for sentence in SENTENCE_RE.split(match["text"]):
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            overlap = question_terms.intersection(_term_counts(sentence).keys())
            if overlap:
                sentences.append((len(overlap), sentence))

    sentences.sort(key=lambda item: item[0], reverse=True)
    selected = []

    for _, sentence in sentences:
        if sentence not in selected:
            selected.append(sentence)
        if len(selected) == 3:
            break

    if not selected:
        selected = [matches[0]["text"][:700].strip()]

    return " ".join(selected)

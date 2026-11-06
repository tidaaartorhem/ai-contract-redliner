"""Shared text utilities: tokenization, bigrams, similarity. Stdlib only."""
import re

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "by",
    "is", "are", "be", "been", "being", "was", "were", "do", "does", "did",
    "have", "has", "had", "having", "it", "its", "this", "that", "these",
    "those", "as", "at", "from", "into", "over", "under", "between", "through",
    "during", "before", "after", "above", "below", "up", "down", "out", "off",
    "about", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "should", "now", "if", "then", "when",
    "where", "which", "who", "whom", "whose", "how", "what", "why", "there",
    "their", "they", "them", "he", "she", "we", "you", "i", "your", "our",
    "my", "me", "us", "him", "her", "his", "hers", "ours", "yours", "theirs",
    "established", "documented", "approved", "communicated", "applied",
    "evaluated", "maintained", "implemented", "defined", "reviewed", "updated",
    "least", "annually", "per", "including", "ensure", "relevant", "according",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def _stem(tok: str) -> str:
    """Light plural stemming so 'biometrics' matches 'biometric' and
    'passkeys' matches 'passkey'. Only strips a trailing 's' (or 'ies'->'y');
    words ending in 'ss' are left alone."""
    if tok.endswith("ies") and len(tok) > 4:
        return tok[:-3] + "y"
    if tok.endswith("s") and not tok.endswith("ss") and len(tok) > 3:
        return tok[:-1]
    return tok


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def bigrams(text: str) -> set[tuple[str, str]]:
    toks = tokens(text)
    return set(zip(toks, toks[1:]))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

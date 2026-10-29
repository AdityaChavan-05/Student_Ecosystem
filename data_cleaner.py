import re
from bs4 import BeautifulSoup


def clean_article_text(text):
    """
    Remove HTML tags and unnecessary whitespace
    from news articles and college notices.
    """
    if not text:
        return ""

    try:
        soup = BeautifulSoup(str(text), "html.parser")
        cleaned_text = soup.get_text(separator=" ", strip=True)
    except Exception:
        cleaned_text = str(text)

    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    return cleaned_text


def limit_text(text, max_length=12000):
    """
    Limit text length to avoid sending excessively long
    content to the AI summarizer.
    """
    cleaned_text = clean_article_text(text)

    try:
        max_length = int(max_length)
    except (TypeError, ValueError):
        max_length = 12000

    if max_length < 1:
        return ""

    if len(cleaned_text) <= max_length:
        return cleaned_text

    return cleaned_text[:max_length].rstrip()

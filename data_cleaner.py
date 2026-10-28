import re
import html
from bs4 import BeautifulSoup

def clean_article_text(text: str) -> str:
"""
Clean HTML and unnecessary whitespace from a news article or notice.

```
Args:
    text: Raw text or HTML content.

Returns:
    Clean, readable plain text.
"""
if not text:
    return ""

# Decode HTML entities such as &amp; and &nbsp;
text = html.unescape(str(text))

# Remove HTML tags and extract readable text
soup = BeautifulSoup(text, "html.parser")

# Remove elements that do not contain useful article text
for element in soup(["script", "style", "noscript"]):
    element.decompose()

text = soup.get_text(separator=" ", strip=True)

# Remove URLs that appear within the extracted text
text = re.sub(r"https?://\S+|www\.\S+", "", text)

# Normalize whitespace
text = re.sub(r"\s+", " ", text)

return text.strip()
```

def limit_text(text: str, max_chars: int = 5000) -> str:
"""
Limit text length before sending it to an AI model.

```
Args:
    text: Input text.
    max_chars: Maximum permitted character count.

Returns:
    Text within the specified character limit.
"""
text = clean_article_text(text)

if max_chars <= 0:
    return ""

if len(text) <= max_chars:
    return text

# Avoid ending in the middle of a word when possible
shortened_text = text[:max_chars]
last_space = shortened_text.rfind(" ")

if last_space > max_chars * 0.8:
    shortened_text = shortened_text[:last_space]

return shortened_text.rstrip() + "..."
```

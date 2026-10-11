from __future__ import annotations

from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def html_to_text(value: str) -> str:
    parser = TextExtractor()
    parser.feed(value or "")
    return " ".join(parser.parts)


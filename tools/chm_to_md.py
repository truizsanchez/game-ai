"""Convert the book's CHM (extracted HTML) into one Markdown file per chapter.

The output is copyrighted material and must stay outside this repository.

Usage:
    uv run tools/chm_to_md.py --chm BOOK.chm --out ../game-ai-private/book-md
    uv run tools/chm_to_md.py --extracted DIR --out ../game-ai-private/book-md

``--chm`` needs a 7-Zip binary (``7zz`` or ``7z``) on PATH or given via ``--sevenzip``.
"""

# /// script
# requires-python = ">=3.12"
# dependencies = ["beautifulsoup4>=4.12"]
# ///

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

BOOK_DIR = "9482final"

# Top-level TOC entries that start a new output file, besides "Chapter N:" and "Appendix X:".
FRONT_MATTER_END = "Chapter 1:"
STANDALONE = {"Last Words", "References", "Bugs and Errata"}
SKIPPED = {"Table of Contents", "BackCover"}
SKIPPED_PREFIXES = ("Index", "List of ")

LUA_HINTS = re.compile(r"^\s*(--|local\s|function\s|end\b)", re.MULTILINE)


@dataclass
class Part:
    slug: str
    title: str
    pages: list[str] = field(default_factory=list)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def read_toc(hhc: Path) -> list[tuple[str, str]]:
    """Return (name, page filename) pairs in reading order."""
    text = hhc.read_text(encoding="latin-1")
    names = re.findall(r'<param name="Name" value="([^"]*)">', text)
    locals_ = re.findall(r'<param name="Local" value="([^"]*)">', text)
    return [(html.unescape(n), Path(p).name) for n, p in zip(names, locals_, strict=True)]


def group_parts(toc: list[tuple[str, str]]) -> list[Part]:
    parts: list[Part] = []
    current: Part | None = Part("00-front-matter", "Front Matter")
    parts.append(current)
    for name, page in toc:
        if name in SKIPPED or name.startswith(SKIPPED_PREFIXES):
            current = None if name.startswith(SKIPPED_PREFIXES) else current
            continue
        if m := re.match(r"Chapter (\d+): (.*)", name):
            current = Part(f"{int(m[1]):02d}-{slugify(m[2])}", name)
            parts.append(current)
        elif m := re.match(r"Appendix ([A-Z]): (.*)", name):
            current = Part(f"appendix-{m[1].lower()}-{slugify(m[2])}", name)
            parts.append(current)
        elif name in STANDALONE:
            current = Part(f"zz-{slugify(name)}", name)
            parts.append(current)
        if current is not None:
            current.pages.append(page)
    return parts


class Converter:
    """Turns one book page (HTML) into Markdown."""

    def __init__(self, images: dict[str, str], lang: str = "cpp") -> None:
        self.images = images  # original image name -> name to reference
        self.lang = lang

    # --- inline -----------------------------------------------------------
    def inline(self, node: Tag | NavigableString) -> str:
        if isinstance(node, NavigableString):
            return re.sub(r"\s+", " ", str(node))
        name = node.name
        cls = node.get("class") or []
        inner = "".join(self.inline(c) for c in node.children)
        if name == "br":
            return "\n"
        if name == "img":
            return self.image(node)
        if name in ("i", "em"):
            return f"*{inner.strip()}*" if inner.strip() else inner
        if name in ("b", "strong"):
            return f"**{inner.strip()}**" if inner.strip() else inner
        if "fixed" in cls or name in ("code", "tt"):
            return f"`{inner.strip()}`" if inner.strip() else inner
        if name == "a" and (href := node.get("href")) and href.startswith(("http", "mailto")):
            return f"[{inner.strip()}]({href})"
        if name == "sup":
            return f"^{inner}"
        if name == "sub":
            return f"_{inner}"
        return inner

    def text(self, node: Tag) -> str:
        return re.sub(r"[ \t]+", " ", "".join(self.inline(c) for c in node.children)).strip()

    def image(self, img: Tag) -> str:
        src = Path(str(img.get("src", ""))).name
        if src not in self.images:
            return ""
        alt = "" if img.get("alt") == "Click To expand" else img.get("alt", "")
        return f"![{alt}](images/{self.images[src]})"

    # --- blocks -----------------------------------------------------------
    def blocks(self, node: Tag) -> list[str]:
        out: list[str] = []
        for child in node.children:
            if isinstance(child, NavigableString):
                if child.strip():
                    out.append(child.strip())
                continue
            out.extend(self.block(child))
        return out

    def block(self, node: Tag) -> list[str]:
        name = node.name
        cls = node.get("class") or []
        if name in ("script", "style"):
            return []
        if name == "table" and node.find("img", alt=re.compile("(Start|End) Sidebar")):
            return []
        if m := re.fullmatch(r"h([1-6])", name or ""):
            return [f"{'#' * int(m[1])} {self.text(node)}"]
        if name == "p":
            t = self.text(node)
            return [t] if t else []
        if name == "pre":
            return [self.code(node)]
        if name in ("ul", "ol"):
            return [self.list_(node)]
        if name == "table" and ({"note", "tip", "warning", "caution", "important"} & set(cls)):
            return [self.admonition(node)]
        if name == "table" and "BlueLine" in cls:
            return []
        if name == "table" and "table" in cls:
            return [self.table(node)]
        if name == "div" and "figure" in cls:
            return [self.figure(node)]
        if name == "div" and "equation" in cls:
            return [self.equation(node)]
        if name == "div" and "sidebar" in cls:
            return [self.sidebar(node)]
        if (name == "div" and "blockquote" in cls) or name == "blockquote":
            return [quote("\n\n".join(self.blocks(node)))]
        if name == "span" and "sidebar-title" in cls:
            return [f"**{node.get_text(' ', strip=True)}**"]
        if name in (
            "div",
            "span",
            "center",
            "font",
            "table",
            "tbody",
            "tr",
            "td",
            "dl",
            "dd",
            "dt",
        ):
            return self.blocks(node)
        if name == "img":
            return [self.image(node)]
        if name == "a":
            return self.blocks(node) if node.find(True) else []
        t = self.text(node)
        return [t] if t else []

    def code(self, pre: Tag) -> str:
        body = pre.get_text().replace("\r", "").strip("\n")
        if self.lang == "lua" and LUA_HINTS.search(body):
            lang = "lua"
        elif "literallayout-normal" in (pre.get("class") or []):
            lang = "text"
        else:
            lang = "cpp"
        return f"```{lang}\n{body}\n```"

    def list_(self, node: Tag, depth: int = 0) -> str:
        lines = []
        for i, li in enumerate(node.find_all("li", recursive=False), 1):
            marker = f"{i}." if node.name == "ol" else "-"
            parts, nested = [], []
            for child in li.children:
                if isinstance(child, Tag) and child.name in ("ul", "ol"):
                    nested.append(self.list_(child, depth + 1))
                elif isinstance(child, Tag):
                    parts.extend(self.block(child))
                elif child.strip():
                    parts.append(child.strip())
            indent = "  " * depth
            body = "\n\n".join(parts).replace("\n", "\n" + indent + "  ")
            lines.append(f"{indent}{marker} {body}")
            lines.extend(nested)
        return "\n".join(lines)

    def table(self, node: Tag) -> str:
        caption = node.find("caption")
        rows = [
            [
                self.text(cell).replace("|", r"\|").replace("\n", " ")
                for cell in tr.find_all(["th", "td"])
            ]
            for tr in node.find_all("tr")
        ]
        rows = [r for r in rows if r]
        if not rows:
            return ""
        width = max(map(len, rows))
        rows = [r + [""] * (width - len(r)) for r in rows]
        md = [f"| {' | '.join(rows[0])} |", f"|{'---|' * width}"]
        md += [f"| {' | '.join(r)} |" for r in rows[1:]]
        title = f"*{self.text(caption)}*\n\n" if caption else ""
        return title + "\n".join(md)

    def figure(self, node: Tag) -> str:
        imgs = [self.image(i) for i in node.find_all("img")]
        title = node.find(class_="figure-title")
        caption = f"\n\n*{self.text(title)}*" if title else ""
        return "\n".join(i for i in imgs if i) + caption

    def equation(self, node: Tag) -> str:
        label = node.find(class_="equation-label")
        imgs = " ".join(self.image(i) for i in node.find_all("img"))
        return f"{imgs} {self.text(label).strip() if label else ''}".strip()

    def admonition(self, node: Tag) -> str:
        title = node.find(class_="admon-title")
        body = node.find(class_="admon-body")
        content = "\n\n".join(self.blocks(body)) if body else ""
        return quote(f"**{self.text(title) if title else 'Note'}:** {content}")

    def sidebar(self, node: Tag) -> str:
        return quote("\n\n".join(b for b in self.blocks(node) if b))


def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def convert_page(path: Path, conv: Converter) -> str:
    soup = BeautifulSoup(path.read_bytes().decode("latin-1"), "html.parser")
    root = soup.find("div", class_=["chapter", "appendix", "preface"]) or soup.body
    # Drop navigation bars (top and bottom tables with "Team LiB"/prev/next images).
    for img in root.find_all("img", alt=re.compile("Team LiB|Previous Section|Next Section")):
        if table := img.find_parent("table"):
            table.decompose()
    md = "\n\n".join(b for b in conv.blocks(root) if b.strip())
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def extract_chm(chm: Path, sevenzip: str, dest: Path) -> None:
    subprocess.run(
        [sevenzip, "x", "-y", f"-o{dest}", str(chm)], check=True, stdout=subprocess.DEVNULL
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--chm", type=Path, help="book .chm file")
    src.add_argument("--extracted", type=Path, help="directory with an already extracted CHM")
    parser.add_argument(
        "--out", type=Path, required=True, help="output directory (outside the repo!)"
    )
    parser.add_argument("--sevenzip", default=shutil.which("7zz") or shutil.which("7z") or "7zz")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        root = args.extracted
        if args.chm:
            root = Path(tmp)
            extract_chm(args.chm, args.sevenzip, root)
        book = root / BOOK_DIR
        hhc = next(root.glob("*.hhc"))

        out: Path = args.out
        (out / "images").mkdir(parents=True, exist_ok=True)
        # Prefer the high-resolution "_0" variants that the CHM links to from thumbnails.
        images: dict[str, str] = {}
        for img in (book / "images").iterdir():
            if img.suffix.lower() in (".jpg", ".gif", ".png") and not img.stem.endswith("_0"):
                big = img.with_name(f"{img.stem}_0{img.suffix}")
                chosen = big if big.exists() else img
                shutil.copy2(chosen, out / "images" / img.name)
                images[img.name] = img.name

        parts = group_parts(read_toc(hhc))
        index = ["# Programming Game AI by Example (Markdown)", ""]
        for part in parts:
            conv = Converter(images, lang="lua" if part.slug.startswith("06-") else "cpp")
            body = "\n---\n\n".join(convert_page(book / p, conv) for p in part.pages)
            (out / f"{part.slug}.md").write_text(body, encoding="utf-8")
            index.append(f"- [{part.title}]({part.slug}.md)")
            print(f"{part.slug}.md: {len(part.pages)} pages")
        (out / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

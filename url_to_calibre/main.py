#!/usr/bin/env python3
import argparse
import configparser
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which
from bs4 import BeautifulSoup
from ebooklib import epub
from newspaper import Article
from rich.console import Console
from rich.logging import RichHandler
import logging
import requests

console = Console()
logging.basicConfig(level=logging.INFO, handlers=[RichHandler(console=console)])
logger = logging.getLogger("url-to-calibre")


def sanitize_filename(title):
    sanitized = re.sub(r"[^\w\s-]", "", title).strip()
    sanitized = re.sub(r"[-\s]+", "_", sanitized)
    return sanitized[:50]


def sanitize_html(html):
    """Clean and structure HTML content"""
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Preserve structural elements
    allowed_tags = [
        "p",
        "br",
        "div",
        "section",
        "article",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "strong",
        "em",
        "blockquote",
        "ul",
        "ol",
        "li",
        "a",
        "img",
    ]

    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.decompose()
        else:
            # Clean attributes but keep basic formatting
            attrs = dict(tag.attrs)
            for attr in list(attrs.keys()):
                if attr not in ["href", "src", "alt", "title"]:
                    del tag.attrs[attr]

    # Add proper paragraph spacing
    for elem in soup.find_all(["p", "br", "div"]):
        elem.append(soup.new_tag("br"))
        elem.insert(0, soup.new_tag("br"))

    return str(soup)


def get_config():
    xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config_dir = xdg_config / "url-to-calibre"
    config_file = config_dir / "config.ini"

    config = configparser.ConfigParser()
    if config_file.exists():
        config.read(config_file)
        return config["DEFAULT"]["calibre_library"]

    config_dir.mkdir(parents=True, exist_ok=True)
    while True:
        library_path = input("Enter path to your Calibre library: ").strip()
        expanded_path = Path(library_path).expanduser()
        if expanded_path.is_dir():
            config["DEFAULT"] = {"calibre_library": str(expanded_path)}
            with open(config_file, "w") as f:
                config.write(f)
            return str(expanded_path)
        print(f"Error: '{expanded_path}' is not a valid directory")


def find_calibre_bin(bin_name):
    paths = [
        "/usr/bin/calibredb",
        "/usr/local/bin/calibredb",
        "/Applications/calibre.app/Contents/MacOS/calibredb",
        str(Path.home() / ".local/bin/calibredb"),
        "C:\\Program Files\\Calibre2\\calibredb.exe",
    ]

    found = which(bin_name)
    if found:
        return found

    for path in paths:
        if Path(path).exists():
            return path
    return None


def check_dependency(bin_name):
    path = find_calibre_bin(bin_name)
    return path if path and Path(path).exists() else False


def create_epub(article, output_path):
    book = epub.EpubBook()
    book.set_identifier(article.url)
    book.set_title(article.title)
    book.set_language("en")

    for author in article.authors:
        book.add_author(author)

    # Get full HTML content
    raw_html = article.article_html or f"<p>{article.text}</p>"
    cleaned_html = sanitize_html(raw_html)

    # Create chapter content
    chapter = epub.EpubHtml(
        title=article.title,
        file_name="content.xhtml",
        content=f"""
        <html>
            <head>
                <title>{article.title}</title>
            </head>
            <body>
                <h1>{article.title}</h1>
                {cleaned_html}
            </body>
        </html>
        """,
    )
    book.add_item(chapter)

    # Add table of contents
    book.toc = (epub.Link("content.xhtml", "Content", "content"),)

    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define spine
    book.spine = ["nav", chapter]

    epub.write_epub(output_path, book, {})


def create_epub_from_html(url, html, output_path):
    book = epub.EpubBook()
    book.set_identifier(url)
    book.set_title(url)
    book.set_language("en")

    # Clean HTML content
    cleaned_html = sanitize_html(html)

    # Create chapter content
    chapter = epub.EpubHtml(
        title=url,
        file_name="content.xhtml",
        content=f"""
        <html>
            <head>
                <title>{url}</title>
            </head>
            <body>
                <h1>{url}</h1>
                {cleaned_html}
            </body>
        </html>
        """,
    )
    book.add_item(chapter)

    # Add table of contents
    book.toc = (epub.Link("content.xhtml", "Content", "content"),)

    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define spine
    book.spine = ["nav", chapter]

    epub.write_epub(output_path, book, {})


def get_system_path():
    env = os.environ.copy()
    if "VIRTUAL_ENV" in env:
        original_path = env.get("PATH", "")
        system_path = ":".join(
            [
                p
                for p in original_path.split(":")
                if "virtualenv" not in p and "venv" not in p
            ]
        )
        env["PATH"] = system_path
    return env


def process_url(url, format, calibre_lib, calibredb_path, ebook_convert_path, results):
    if url.lower().endswith(".pdf"):
        try:
            response = requests.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"Warning: Failed to download PDF from {url}: {e}")
            results["failed"].append(url)
            return

        sanitized_title = sanitize_filename(Path(url).stem) or "untitled"
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / f"{sanitized_title}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(response.content)

            if format != "pdf":
                if not ebook_convert_path:
                    logger.warning("Warning: ebook-convert not found. Install Calibre first.")
                    results["failed"].append(url)
                    return

                output_path = Path(tmpdir) / f"{sanitized_title}.{format}"
                try:
                    subprocess.run(
                        [ebook_convert_path, pdf_path, output_path],
                        check=True,
                        env=get_system_path(),
                    )
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Warning: Conversion failed for {url}: {e}")
                    results["failed"].append(url)
                    return
            else:
                output_path = pdf_path

            try:
                subprocess.run(
                    [calibredb_path, "add", "--library-path", calibre_lib, output_path],
                    check=True,
                    env=get_system_path(),
                )
                logger.info(f"Successfully added to Calibre: {sanitized_title}")
                results["success"].append(sanitized_title)
            except subprocess.CalledProcessError as e:
                logger.warning(f"Warning: Error adding to Calibre for {url}: {e}")
                results["failed"].append(url)
        return

    article = Article(url, keep_article_html=True)
    try:
        article.download()
        article.parse()
    except Exception as e:
        logger.warning(f"Warning: Failed to download article from {url}: {e}")
        results["failed"].append(url)
        return

    if not article.title or not article.text:
        logger.warning(f"Warning: Could not extract meaningful content from URL: {url}")
        try:
            response = requests.get(url)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            logger.warning(f"Warning: Failed to download HTML from {url}: {e}")
            results["failed"].append(url)
            return

        sanitized_title = sanitize_filename(url) or "untitled"
        with tempfile.TemporaryDirectory() as tmpdir:
            epub_path = Path(tmpdir) / f"{sanitized_title}.epub"
            create_epub_from_html(url, html, epub_path)

            if format != "epub":
                if not ebook_convert_path:
                    logger.warning("Warning: ebook-convert not found. Install Calibre first.")
                    results["failed"].append(url)
                    return

                output_path = Path(tmpdir) / f"{sanitized_title}.{format}"
                try:
                    subprocess.run(
                        [ebook_convert_path, epub_path, output_path],
                        check=True,
                        env=get_system_path(),
                    )
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Warning: Conversion failed for {url}: {e}")
                    results["failed"].append(url)
                    return
            else:
                output_path = epub_path

            try:
                subprocess.run(
                    [calibredb_path, "add", "--library-path", calibre_lib, output_path],
                    check=True,
                    env=get_system_path(),
                )
                logger.info(f"Successfully added to Calibre: {sanitized_title}")
                results["success"].append(sanitized_title)
            except subprocess.CalledProcessError as e:
                logger.warning(f"Warning: Error adding to Calibre for {url}: {e}")
                results["failed"].append(url)
        return

    sanitized_title = sanitize_filename(article.title) or "untitled"
    with tempfile.TemporaryDirectory() as tmpdir:
        epub_path = Path(tmpdir) / f"{sanitized_title}.epub"
        create_epub(article, epub_path)

        if format != "epub":
            if not ebook_convert_path:
                logger.warning("Warning: ebook-convert not found. Install Calibre first.")
                results["failed"].append(url)
                return

            output_path = Path(tmpdir) / f"{sanitized_title}.{format}"
            try:
                subprocess.run(
                    [ebook_convert_path, epub_path, output_path],
                    check=True,
                    env=get_system_path(),
                )
            except subprocess.CalledProcessError as e:
                logger.warning(f"Warning: Conversion failed for {url}: {e}")
                results["failed"].append(url)
                return
        else:
            output_path = epub_path

        try:
            subprocess.run(
                [calibredb_path, "add", "--library-path", calibre_lib, output_path],
                check=True,
                env=get_system_path(),
            )
            logger.info(f"Successfully added to Calibre: {article.title}")
            results["success"].append(article.title)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Warning: Error adding to Calibre for {url}: {e}")
            results["failed"].append(url)


def main():
    parser = argparse.ArgumentParser(description="Convert web articles to ebooks")
    parser.add_argument("url", nargs="*", help="URL(s) of the article(s) to convert")
    parser.add_argument(
        "-f",
        "--format",
        choices=["epub", "mobi", "azw3"],
        default="epub",
        help="Output format",
    )
    args = parser.parse_args()

    calibre_lib = get_config()
    calibredb_path = check_dependency("calibredb")
    ebook_convert_path = check_dependency("ebook-convert")

    if not calibredb_path:
        logger.error(
            """Error: calibredb not found. Ensure Calibre is installed.
Install command-line tools from Calibre preferences:
1. Open Calibre
2. Preferences → Advanced → Miscellaneous
3. Click 'Install command line tools'"""
        )
        sys.exit(1)

    urls = args.url if args.url else [line.strip() for line in sys.stdin if line.strip()]
    results = {"success": [], "failed": []}
    for url in urls:
        process_url(url, args.format, calibre_lib, calibredb_path, ebook_convert_path, results)

    console.print(f"\n[bold green]Books successfully added: {len(results['success'])}[/bold green]")
    console.print(f"\n[bold red]Books failed to add: {len(results['failed'])}[/bold red]")

if __name__ == "__main__":
    main()


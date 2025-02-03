# URL to Calibre

Python script to convert a URL's content to ebook format and send directly to [Calibre](https://github.com/kovidgoyal/calibre) library.

## Installation

### Prerequisites

You'll need [Calibre](https://github.com/kovidgoyal/calibre) and you'll need to know where your Calibre library is stored.

Run:

```shell
pip install url-to-calibre
```

If you're on a system that doesn't let you install Python packages outside of a virtual environment, run:

```shell
pipx install url-to-calibre
```

## Usage

To generate an epub file:

```shell
url-to-calibre <URL>
```

You can specify other formats (`mobi` or `azw3`) via the `--format` (or `-f`) parameter, for example:

```shell
url-to-calibre <URL> -f mobi
```

## Todo

- Take multiple URLs as arguments.
- Allow input via STDIN so user can pass a file full of URLs.

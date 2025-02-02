# URL to Calibre

Python script to convert a URL's content to ebook format and send directly to [Calibre](https://github.com/kovidgoyal/calibre) library.

## Installation

1. Clone the repo and enter the folder
2. Run `poetry build`
3. Run `poetry install`

## Usage

To generate an epub file:

```shell
url-to-calibre <URL>
```

You can specify other formats (`mobi` or `azw3`) via the `--format` (or `-f`) parameter, for example:

```shell
url-to-calibre <URL> -f mobi
```

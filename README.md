# URL to Calibre

Python script to convert a URL's content to ebook format and send directly to [Calibre](https://github.com/kovidgoyal/calibre) library.

## Usage

To generate an epub file:

```shell
python app.py <URL>
```

You can specify other formats (`mobi` or `azw3`) via the `--format` (or `-f`) parameter, for example:

```shell
python app.py <URL> -f mobi
```

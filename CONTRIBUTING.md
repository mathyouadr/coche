# Contributing to Coche

Thanks for helping! Coche aims to stay small, dependency-free and pleasant to read.

## Ground rules

- **Standard library only** on the server, **no build step** in the browser (plain `app.js` / `app.css`).
- Pure functions for parsing (dates, Quick Add, filters) with unit tests next to them.
- Keep the `/api/v1` endpoints compatible with the Todoist API v1: same paths, same field names.
- Every user-facing string goes through `t("English text")` in `app.js`, with its translation in `static/i18n.js`.

## Getting started

```bash
git clone https://github.com/mathyouadr/coche.git && cd coche
COCHE_DATA_DIR=./data python3 -m coche demo      # sample tasks
COCHE_DATA_DIR=./data python3 -m coche           # http://127.0.0.1:8043
python3 -m unittest discover -s tests -t . -v    # the test suite
```

Static files are served with a content hash, so a page reload always picks up your edits to `app.js` or `app.css`.

## Ideas that are welcome

- **New languages**: copy `static/i18n.js` (UI) and add the words to `dates.py` (date parser), plus a few test cases in `tests/test_dates.py`.
- Date expressions Coche doesn't understand yet: open an issue with the exact text you typed and what you expected.
- Accessibility and mobile polish.

## Pull requests

1. One topic per PR, with a short description of the why.
2. Tests pass (`python3 -m unittest discover -s tests -t .`).
3. For UI changes, add a screenshot (phone and desktop if the layout changes).

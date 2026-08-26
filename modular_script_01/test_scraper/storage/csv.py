"""
CSV helpers for the unified datasets.

`professor_master.csv` holds one row per professor and `publications.csv`
holds one row per paper.  Rows are written with utf-8-sig so Excel opens
them cleanly, and lists inside cells are joined with '; '.
"""

import os

import pandas as pd


def _norm(value):
    if isinstance(value, (list, tuple, set)):
        return '; '.join(str(v) for v in value)
    if value is None:
        return ''
    return value


def write_rows(rows, path: str) -> None:
    """Write rows to `path`, overwriting any existing file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame(rows)
    if not df.empty:
        for col in df.columns:
            df[col] = df[col].apply(_norm)
    df.to_csv(path, index=False, encoding='utf-8-sig')


def append_rows(rows, path: str) -> None:
    """Append rows to `path`, creating the file with a header if needed."""
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame(rows)
    for col in df.columns:
        df[col] = df[col].apply(_norm)
    exists = os.path.exists(path)
    df.to_csv(path, index=False, encoding='utf-8-sig',
              mode='a' if exists else 'w',
              header=not exists)


def read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    except (ValueError, OSError):
        return pd.DataFrame()


def load_csv_rows(path: str) -> list:
    """Return the CSV as a list of plain dicts (all values as strings)."""
    df = read_csv(path)
    if df.empty:
        return []
    return df.to_dict('records')


def dedupe_csv(path: str, key_col: str, keep: str = 'first') -> int:
    """
    Remove duplicate rows from `path` in place.

    Args:
        path: CSV file to dedupe.
        key_col: column used to detect duplicates.
        keep: 'first' or 'last'.

    Returns:
        Number of rows removed.
    """
    if not os.path.exists(path):
        return 0
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.empty or key_col not in df.columns:
        return 0
    before = len(df)
    df = df.drop_duplicates(subset=[key_col], keep=keep)
    removed = before - len(df)
    df.to_csv(path, index=False, encoding='utf-8-sig')
    return removed


def _row_score(row) -> int:
    return sum(1 for v in row.to_dict().values() if isinstance(v, str) and v.strip())


def dedupe_best(path: str, key_col: str) -> int:
    """
    Keep the most complete row per `key_col` (most non-empty cells).

    This ensures a later, poorer collection never overwrites a richer one.

    Returns:
        Number of rows removed.
    """
    if not os.path.exists(path):
        return 0
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.empty or key_col not in df.columns:
        return 0
    before = len(df)
    df['_score'] = df.apply(_row_score, axis=1)
    df = df.sort_values('_score').drop_duplicates(subset=[key_col], keep='last')
    df = df.drop(columns=['_score'])
    removed = before - len(df)
    df.to_csv(path, index=False, encoding='utf-8-sig')
    return removed

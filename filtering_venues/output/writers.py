"""CSV output writers."""

import csv

FIELDS = [
    "University",
    "Rank",
    "Professor name",
    "Title",
    "Email",
    "Mail",
    "Lab link",
    "Research area",
    "is_pickable",
    "Matched_venues",
    "N_target_pubs",
    "Total_publications",
    "profile_url",
]


def _clean_row(row):
    return {k: (row.get(k, "") if row.get(k) is not None else "") for k in FIELDS}


def write_csv(path, rows):
    """Write rows (list of dicts) to a CSV file. utf-8-sig so Excel opens it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_clean_row(row))


class StreamingCsvWriter:
    """Writes rows to a CSV file as they arrive (flushes after each row)."""

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fh = open(path, "w", newline="", encoding="utf-8-sig")
        self._writer = csv.DictWriter(self._fh, fieldnames=FIELDS, extrasaction="ignore")
        self._writer.writeheader()
        self._fh.flush()
        self.count = 0

    def write(self, row):
        self._writer.writerow(_clean_row(row))
        self._fh.flush()
        self.count += 1

    def close(self):
        self._fh.close()

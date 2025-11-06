import csv
import datetime as dt
import re
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
TABLET_CSV = BASE_DIR / "tablet.csv"
UNITS_ROWS_CSV = BASE_DIR / "units_rows.csv"


def read_csv_rows(path: Path):
    # Try UTF-8 first, fallback to latin-1 due to special chars in the sheet
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                return list(reader)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Unable to decode CSV at {path}")


def parse_units_from_tablet(rows):
    """
    Parse the multi-section spreadsheet export into a structured dict.

    Extract for each (bloco, unidade): tipologia, AHB, ABE, preço, piso, luz_natural, score.
    We rely on two sections per bloco:
      1) Listing of units starting with a row whose col0 is 'Bloco X' and col1 like 'A t1'.
      2) A scoring matrix starting with 'Bloco X,,A,B,C,...' followed by rows 'Luz Natural', 'Piso', 'Pontua...'.
    If multiple repeated sections exist, the last occurrence wins.
    """
    units = {}  # (bloco)-> { unidade_letter -> data }

    # Helper regexes
    price_re = re.compile(r"^\d{1,3}(?:,\d{3})+(?:\.\d+)?$")  # e.g., 300,104 or 1,234,567.89

    i = 0
    n = len(rows)
    while i < n:
        row = rows[i]
        if not row:
            i += 1
            continue

        first = (row[0] or "").strip() if len(row) > 0 else ""
        if first.startswith("Bloco ") and len(row) > 1 and (row[1] or "").strip():
            # Possible start of a unit listing section for this bloco
            try:
                bloco_num = int(first.split()[1].strip(":"))
            except Exception:
                bloco_num = (first.split()[1] if len(first.split()) > 1 else first)

            units.setdefault(bloco_num, {})

            # Consume this and following rows that have same section (col0 empty) but carry unit data
            j = i
            while j < n:
                r = rows[j]
                if not r:
                    j += 1
                    continue
                col0 = (r[0] or "").strip() if len(r) > 0 else ""
                # Stop when next bloco header appears for a new section like 'Bloco 1,,A,B,...' (matrix)
                # or when another section starts again with 'Optimiza' etc.
                if col0.startswith("Optimiza"):
                    break
                if col0.startswith("Bloco ") and j != i:
                    # Next bloco section (either unit list or matrix); stop current list
                    break

                # Expect unit lines when column 1 has something like 'A t1'
                if (len(r) >= 2) and (r[1] or "").strip():
                    unit_field = r[1].strip()
                    # unit_field examples: 'A t1', 'H t3 D'
                    parts = unit_field.split()
                    unidade = parts[0].strip(",;")
                    tipologia = " ".join(parts[1:]) if len(parts) > 1 else ""
                    tipologia = tipologia.upper().replace("T", "T", 1)  # normalize leading t->T
                    if tipologia and not tipologia.startswith("T"):
                        tipologia = tipologia  # keep as-is if unusual format

                    # Extract AHB and ABE values if present
                    ahb = None
                    abe = None
                    # From observed layout: indices 4 and 5
                    if len(r) > 5:
                        try:
                            ahb = float(str(r[4]).replace(",", "."))
                        except Exception:
                            ahb = None
                        try:
                            abe = float(str(r[5]).replace(",", "."))
                        except Exception:
                            abe = None

                    # Extract price: prefer last price-like token before a percent field
                    preco = None
                    for val in r:
                        sval = (val or "").strip().strip("\"")
                        if sval.endswith("%"):
                            # Stop tracking when percentages start; typically area % column follows price
                            continue
                        if price_re.match(sval):
                            preco = sval
                    # Fallback: try to find a large integer or decimal with comma separators
                    if preco is None:
                        for val in r[::-1]:
                            sval = (val or "").strip().strip("\"")
                            if price_re.match(sval):
                                preco = sval
                                break

                    # Temporary store; scoring will fill luz_natural and score later
                    units[bloco_num][unidade] = {
                        "tipologia": tipologia.strip(),
                        "AHB": ahb,
                        "ABE": abe,
                        "preco": preco,
                        # placeholders
                        "piso": None,
                        "luz_natural": None,
                        "score": None,
                    }

                j += 1

            i = j
            continue

        # Scoring matrix: 'Bloco X,,A,B,C,...' then feature rows
        if first.startswith("Bloco ") and len(row) > 2 and not (row[1] or "").strip():
            try:
                bloco_num = int(first.split()[1].strip(":"))
            except Exception:
                bloco_num = (first.split()[1] if len(first.split()) > 1 else first)

            # Determine column mapping for units
            headers = row
            unit_cols = []  # list of (col_index, unidade_letter)
            for idx in range(2, len(headers)):
                u = (headers[idx] or "").strip()
                if u:
                    unit_cols.append((idx, u))

            j = i + 1
            while j < n:
                r = rows[j]
                if not r:
                    j += 1
                    continue
                label = (r[1] or "").strip() if len(r) > 1 else ""
                if (r[0] or "").startswith("Bloco "):
                    break  # next bloco section
                if (r[0] or "").startswith("Optimiza"):
                    break  # header repeating

                key = label.lower()
                for col_idx, unidade in unit_cols:
                    if len(r) <= col_idx:
                        continue
                    val = (r[col_idx] or "").strip()
                    if not val:
                        continue
                    try:
                        num = float(str(val).replace(",", "."))
                    except Exception:
                        continue
                    # Update only if unit already known
                    if bloco_num in units and unidade in units[bloco_num]:
                        if key.startswith("luz natural"):
                            units[bloco_num][unidade]["luz_natural"] = int(num)
                        elif key.startswith("piso"):
                            units[bloco_num][unidade]["piso"] = int(num)
                        elif key.startswith("pontua"):
                            units[bloco_num][unidade]["score"] = int(num)
                j += 1

            i = j
            continue

        i += 1

    return units


def load_existing_units(path: Path):
    existing = {}
    max_id = 0
    header = []
    if not path.exists():
        return header, existing, max_id
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        for row in reader:
            try:
                rid = int(row.get("id") or 0)
            except Exception:
                rid = 0
            max_id = max(max_id, rid)
            key = (str(row.get("bloco") or "").strip(), (row.get("unidade") or "").strip())
            existing[key] = row
    return header, existing, max_id


def normalize_tipologia(t: str) -> str:
    if not t:
        return t
    t = t.strip().upper()
    # Ensure it starts with T when it looks like a typology
    if re.match(r"^T\d", t):
        return t
    if re.match(r"^\d", t):
        return "T" + t
    return t


def format_area(val):
    if val is None:
        return ""
    return f"{val:.2f} m2"


def parse_price_to_int(s):
    if not s:
        return ""
    s = str(s).replace(",", "")
    s = s.strip()
    # If it still has decimals, round to nearest int
    try:
        if "." in s:
            return str(int(round(float(s))))
        return str(int(s))
    except Exception:
        return ""


def upsert_units():
    rows = read_csv_rows(TABLET_CSV)
    parsed = parse_units_from_tablet(rows)

    header, existing, max_id = load_existing_units(UNITS_ROWS_CSV)
    if not header:
        header = [
            "id",
            "created_at",
            "unidade",
            "tipologia",
            "bloco",
            "piso",
            "AHB",
            "ABE",
            "pre��o",
            "luz_natural",
            "score",
        ]

    now = dt.datetime.now(dt.UTC).isoformat()

    # Resolve the actual header key used for price (handles mojibake on 'preço')
    def norm_ascii(s: str) -> str:
        return "".join(ch for ch in (s or "").lower() if "a" <= ch <= "z")

    price_key = None
    for h in header:
        nh = norm_ascii(h)
        if nh.startswith("preco") or nh.startswith("pre"):
            price_key = h
            break
    if price_key is None:
        # Fallback to a best-effort new key name matching schema intent
        price_key = "preco"
        if price_key not in header:
            header.append(price_key)

    # Build new/updated rows
    for bloco_num, units_in_block in parsed.items():
        bloco_str = str(bloco_num)
        for unidade, data in units_in_block.items():
            key = (bloco_str, unidade)
            row = existing.get(key)
            if row is None:
                max_id += 1
                row = {h: "" for h in header}
                row["id"] = str(max_id)
                row["created_at"] = now
            # Update fields
            row["unidade"] = unidade
            row["tipologia"] = normalize_tipologia(data.get("tipologia") or "")
            row["bloco"] = bloco_str
            if data.get("piso") is not None:
                row["piso"] = str(int(data["piso"]))
            row["AHB"] = format_area(data.get("AHB"))
            row["ABE"] = format_area(data.get("ABE"))
            row[price_key] = parse_price_to_int(data.get("preco"))
            if data.get("luz_natural") is not None:
                row["luz_natural"] = str(int(data["luz_natural"]))
            if data.get("score") is not None:
                row["score"] = str(int(data["score"]))

            existing[key] = row

    # Write back CSV in a stable order: by bloco then unidade
    out_rows = list(existing.items())
    out_rows.sort(key=lambda kv: (kv[0][0], kv[0][1]))

    with UNITS_ROWS_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for _, row in out_rows:
            writer.writerow(row)


if __name__ == "__main__":
    upsert_units()

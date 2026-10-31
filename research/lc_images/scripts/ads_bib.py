"""Reemplaza las entradas @misc de arXiv de un refs.bib por la BibTeX de ADS (si esta publicada).

Uso: python ads_bib.py refs.bib token_file [--dry]
(token_file: archivo con la llave de la API de ADS; no versionarlo.)
Mantiene la clave de cita original. Imprime una tabla eprint -> bibcode, revista.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

bib_path, tok_path = sys.argv[1], sys.argv[2]
dry = "--dry" in sys.argv
TOKEN = open(tok_path).read().strip()
API = "https://api.adsabs.harvard.edu/v1"
# Se citan versiones de arXiv que no son la publicada.
SKIP = {"2305.13745": "sin revista: la publicada (RAA 25, 115008) es LightCurve MoE, no la v1 citada"}


def ads(path, data=None):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {TOKEN}",
                                                      "Content-Type": "application/json"},
                                 data=json.dumps(data).encode() if data else None)
    with urllib.request.urlopen(req, timeout=60) as f:
        return json.load(f)


text = open(bib_path, encoding="utf-8").read()
entries = re.split(r"\n(?=@)", text.strip())
out, rows = [], []
for e in entries:
    key = re.match(r"@\w+\{([^,]+),", e).group(1)
    m = re.search(r"eprint=\{([^}]+)\}", e)
    if not m:
        out.append(e)
        rows.append((key, "", "sin eprint", ""))
        continue
    eid = m.group(1)
    if eid in SKIP:
        out.append(e)
        rows.append((key, eid, "se deja en arXiv", SKIP[eid]))
        continue
    q = urllib.parse.quote(f"identifier:arXiv:{eid}")
    docs = ads(f"/search/query?q={q}&fl=bibcode,pub,property,doctype")["response"]["docs"]
    time.sleep(0.3)
    if not docs:
        out.append(e)
        rows.append((key, eid, "no está en ADS", ""))
        continue
    d = docs[0]
    refereed = "REFEREED" in d.get("property", [])
    if not refereed:
        out.append(e)
        rows.append((key, eid, d["bibcode"], f"sin revista ({d.get('pub', '')})"))
        continue
    bt = ads("/export/bibtex", {"bibcode": [d["bibcode"]]})["export"].strip()
    bt = re.sub(r"^(@\w+\{)[^,]+,", lambda mm: mm.group(1) + key + ",", bt, count=1)
    out.append(bt)
    rows.append((key, eid, d["bibcode"], d.get("pub", "")))
    time.sleep(0.3)

for r in rows:
    print(" | ".join(r))
print(f"\nrevista: {sum(1 for r in rows if r[3] and not r[3].startswith('sin'))} de {len(rows)}")
if not dry:
    open(bib_path, "w", encoding="utf-8").write("\n\n".join(out) + "\n")

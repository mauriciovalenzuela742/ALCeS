"""Corre las cadenas de la revision en ADS: conteo y primeros resultados que no estan en refs.bib.

Uso: python ads_search.py refs.bib token_file out.json
(token_file: archivo con la llave de la API de ADS; no versionarlo.)
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

bib, tok, out = sys.argv[1:4]
TOKEN = open(tok).read().strip()
FILTER = "year:2015-2026 collection:astronomy"
QUERIES = [
    (1, 'abs:("Gaussian process" AND (heatmap OR "convolutional neural network") AND supernova AND classification)'),
    (2, 'abs:("light curve" AND (image OR "2D") AND ("convolutional neural network" OR CNN OR "vision transformer") AND (transient OR supernova) AND classification)'),
    (3, 'abs:(kilonova AND (classification OR classifier) AND (LSST OR Rubin OR ZTF) AND photometric)'),
    (4, 'abs:(("Gramian angular" OR "recurrence plot" OR "Markov transition field") AND "light curve")'),
    (5, 'abs:(ALeRCE AND transformer)'),
    (6, 'abs:(ELAsTiCC)'),
    (7, 'abs:((transformer OR "recurrent neural network" OR GRU OR LSTM) AND ("convolutional neural network" OR CNN) AND "light curve" AND (transient OR supernova) AND classification)'),
    (8, 'abs:(("dm-dt" OR dmdt) AND "light curve")'),
    (9, 'abs:(kilonova AND (Kasen OR Bulla) AND (classification OR classifier))'),
    (10, 'abs:(ALeRCE AND classifier)'),
    (12, 'abs:((leakage OR "data leakage") AND (template OR simulation) AND (classification OR classifier) AND (transient OR supernova OR "light curve"))'),
    (13, 'abs:("vision transformer" AND "light curve")'),
    (14, 'abs:(Fink AND kilonova)'),
    (15, 'abs:(PLAsTiCC AND classification)'),
    (16, 'abs:((cadence OR "observing strategy") AND (LSST OR Rubin) AND "photometric classification")'),
    (20, 'abs:("early classification" AND (transient OR supernova OR kilonova) AND (LSST OR ZTF OR Rubin))'),
    (21, 'abs:(kilonova AND (model OR models) AND (distinguish OR discriminate OR "model selection" OR "model comparison") AND ("light curve" OR photometric) AND (LSST OR Rubin))'),
    (22, 'abs:((sparse OR "few epochs" OR "number of observations" OR "number of detections") AND "light curve" AND classification AND (transient OR supernova) AND (LSST OR Rubin))'),
]


def search(q, rows=25):
    url = ("https://api.adsabs.harvard.edu/v1/search/query?" +
           urllib.parse.urlencode({"q": q, "fq": FILTER, "rows": rows, "sort": "score desc",
                                   "fl": "bibcode,title,identifier,citation_count,year,property"}))
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=60) as f:
        return json.load(f)["response"]


have = set(re.findall(r"eprint\s*=\s*\{([^}]+)\}", open(bib, encoding="utf-8").read()))
have |= set(re.findall(r"arXiv:(\d{4}\.\d{4,5})", open(bib, encoding="utf-8").read()))
res = []
for n, q in QUERIES:
    r = search(q)
    new = []
    for d in r["docs"]:
        ax = next((i[6:] for i in d.get("identifier", []) if i.startswith("arXiv:")), "")
        if ax and ax in have:
            continue
        new.append({"bibcode": d["bibcode"], "arxiv": ax, "year": d.get("year"),
                    "cites": d.get("citation_count", 0), "refereed": "REFEREED" in d.get("property", []),
                    "title": (d.get("title") or [""])[0]})
    res.append({"n": n, "q": q, "numFound": r["numFound"], "new_in_top25": new})
    print(f"#{n}: {r['numFound']} resultados; {len(new)} de los 25 primeros no estan en refs.bib")
    time.sleep(0.5)
json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

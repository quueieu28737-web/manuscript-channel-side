"""Fetch OpenAlex seed records and citing-work metadata, once per request."""
import datetime
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.openalex.org/works/https://doi.org/"
DOIS = ["10.1109/TIFS.2025.3622954", "10.48550/arXiv.2409.20002", "10.48550/arXiv.2608.09225"]
output = {"retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "seeds": []}
for doi in DOIS:
    rec = {"doi_requested": doi, "work_query": BASE + doi}
    try:
        with urllib.request.urlopen(rec["work_query"], timeout=25) as response:
            work = json.load(response)
        rec["work"] = {k: work.get(k) for k in ("id", "doi", "display_name", "cited_by_count", "cited_by_api_url", "ids")}
        workid = work["id"].rsplit("/", 1)[-1]
        rec["citing_query"] = "https://api.openalex.org/works?" + urllib.parse.urlencode({"filter": "cites:" + workid, "per-page": "200", "select": "id,doi,display_name,publication_date,primary_location,ids"})
        with urllib.request.urlopen(rec["citing_query"], timeout=25) as response:
            cited = json.load(response)
        rec["meta"] = cited.get("meta")
        rec["results"] = cited.get("results", [])
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    output["seeds"].append(rec)
path = pathlib.Path(__file__).resolve().parents[1] / "data/r35-openalex-pilot.json"
path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
for item in output["seeds"]:
    print(item["doi_requested"], item.get("work", {}).get("id"), item.get("work", {}).get("cited_by_count"), len(item.get("results", [])), item.get("error", ""))

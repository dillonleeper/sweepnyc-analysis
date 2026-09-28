"""Fetch current reference evidence, separately from the frozen pilot inputs."""

import sys, json, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sweepnyc.socrata import metadata, fetch_rows

OUT = ROOT / "data/raw/validation"
QUERIES = {
    "address_points": (
        "uf93-f8nk",
        "boroughcode='1'",
        "addresspointid,bin,house_number,house_number_suffix,house_number_range,house_number_range_suffix,full_street_name,zipcode,address_status,validation,special_condition,address_source,the_geom",
    ),
    "cscl_geometry": (
        "inkn-q76z",
        "boroughcode='1'",
        "physicalid,full_street_name,stname_label,street_name,l_low_hn,l_high_hn,r_low_hn,r_high_hn,l_zip,r_zip,status,continuous_parity_flag,twisted_parity_flag,rw_type,b5sc,l_blockfaceid,r_blockfaceid,created_date,modified_date,the_geom",
    ),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {},
    }
    for name, (ds, where, select) in QUERIES.items():
        meta = metadata(ds)
        (OUT / f"{name}_metadata.json").write_text(json.dumps(meta, indent=2))
        rows = []
        while True:
            page = fetch_rows(
                ds,
                where=where,
                select=select,
                order=":id",
                limit=10000,
                offset=len(rows),
            )
            rows.extend(page)
            print(name, len(rows), flush=True)
            if len(page) < 10000:
                break
        payload = json.dumps(rows, sort_keys=True).encode()
        (OUT / f"{name}.json").write_bytes(payload)
        manifest["sources"][name] = {
            "dataset_id": ds,
            "where": where,
            "select": select,
            "order": ":id",
            "rows": len(rows),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "rows_updated_at": meta.get("rowsUpdatedAt"),
        }
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

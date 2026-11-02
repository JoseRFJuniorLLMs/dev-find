from __future__ import annotations

import argparse
import json
import logging

from .app import DevFind
from .config import Settings
from .catalog import import_cities, export_catalog
from .registry import import_cnpj
from .receita_sync import sync_cnpj


def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="dev-find")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("init-db")
    scan=sub.add_parser("scan")
    scan.add_argument("--city",required=True)
    scan.add_argument("--state",required=True)
    sub.add_parser("send-once")
    sub.add_parser("daemon")
    sub.add_parser("status")
    coverage=sub.add_parser("import-cities")
    coverage.add_argument("--state")
    coverage.add_argument("--all-states",action="store_true")
    catalog=sub.add_parser("export-catalog")
    catalog.add_argument("--output",required=True)
    registry=sub.add_parser("import-cnpj")
    registry.add_argument("--establishments",type=__import__("pathlib").Path,nargs="+",required=True)
    registry.add_argument("--municipalities",type=__import__("pathlib").Path,required=True)
    registry.add_argument("--companies",type=__import__("pathlib").Path,nargs="+",required=True)
    registry.add_argument("--state")
    sub.add_parser("sync-cnpj")
    add=sub.add_parser("add-city")
    add.add_argument("city")
    add.add_argument("state")
    add.add_argument("--priority",type=int,default=50)
    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args=build_parser().parse_args()
    settings=Settings()
    app=DevFind(settings)

    if args.command=="init-db":
        app.db.init()
        app.db.seed_cities(settings.cities_file)
        out=app.db.stats()
    elif args.command=="scan":
        out=app.scan_city(args.city,args.state)
    elif args.command=="send-once":
        out=app.send_once()
    elif args.command=="daemon":
        app.daemon()
        return
    elif args.command=="status":
        out=app.db.stats()
    elif args.command=="import-cities":
        out={"cities":import_cities(app.db,args.state)}
    elif args.command=="export-catalog":
        from pathlib import Path
        out={"rows":export_catalog(app.db,Path(args.output))}
    elif args.command=="import-cnpj":
        out=import_cnpj(app.db,args.establishments,args.municipalities,args.companies,args.state)
    elif args.command=="sync-cnpj":
        out=sync_cnpj(app.db,settings.db_path.parent/"cnpj-cache")
    else:
        app.db.add_city(args.city,args.state,args.priority)
        out={"added":f"{args.city}/{args.state}","priority":args.priority}
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))

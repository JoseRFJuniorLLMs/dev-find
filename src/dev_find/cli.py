from __future__ import annotations

import argparse
import json
import logging

from .app import DevFind
from .config import Settings


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
    else:
        app.db.add_city(args.city,args.state,args.priority)
        out={"added":f"{args.city}/{args.state}","priority":args.priority}
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))

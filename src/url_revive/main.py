import colorlog
import logging
from colorama import Fore,Style
from url_revive.archive_reader import fetch_cdx_snapshots, fetch_memento_snapshots
from url_revive.cli_parser import parse_args 
from url_revive.networking import RequestThrottler

def query_wayback(urls, limit, match_codes, raw=False, unique=False):
    for url in urls:
        logging.info(f'Fetching wayback snapshot(s) for {url}')
        snapshots = fetch_cdx_snapshots(url, limit, match_codes, raw=raw, unique=unique)
        for snapshot in snapshots:
            yield snapshot

def query_memento(urls, limit, match_codes):
    for url in urls:
        logging.info(f'Fetching memento snapshot(s) for {url}')
        snapshots = fetch_memento_snapshots(url, limit, match_codes)
        for snapshot in snapshots:
            yield snapshot

def dump_snapshots(snapshots):
    request_throttler = RequestThrottler(1)
    for snapshot in snapshots:
        dump_snapshot(snapshot, request_throttler) 

def dump_snapshot(snapshot, request_throttler):
    url = snapshot.url
    response = request_throttler.safe_get(url)
    if not response:
        logging.error(f'Failed to dump snapshot')
    else:
        print(response.text)

def pretty_print(snapshot, color=True):
    status_code = int(snapshot.status) // 100
    match status_code:
        case 1:
            status_color = Fore.WHITE
        case 2:
            status_color = Fore.GREEN 
        case 3:
            status_color = Fore.YELLOW 
        case 4:
            status_color = Fore.RED
        case 5:
            status_color = Fore.MAGENTA
    if color: 
        status_display = f'{status_color}{snapshot.status}{Style.RESET_ALL}'
    else:
        status_display = f'{snapshot.status}'
    print(f'{snapshot.url} [{status_display}]')

def setup_logger(silent, no_color):
    logging.getLogger("pyrate_limiter").setLevel(logging.CRITICAL)
    logging_level = logging.WARNING if silent else logging.INFO

    logger = logging.getLogger()
    logger.setLevel(logging_level)
    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        "[%(log_color)s%(levelname)s%(reset)s] %(blue)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG'    :   'blue',
            'INFO'     :   'green',
            'WARNING'  :   'yellow',
            'ERROR'    :   'red',
            'CRITICAL' :   'bold_red',
        }
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def main():
    args = parse_args() 
    setup_logger(args.silent, args.no_color)
    request_throttler = RequestThrottler(4)

    if args.memento:
        queries = query_memento(args.urls, args.limit, args.match_codes)
    else:
        queries = query_wayback(args.urls, args.limit, args.match_codes, raw=args.raw, unique=args.unique)

    for query in queries:
        for snapshot in query:
            if snapshot.status == '-': #exclude continuation
                continue
            pretty_print(snapshot, color= not args.no_color)
            if args.dump:
                dump_snapshot(snapshot, request_throttler)

if __name__ == "__main__":
    main()

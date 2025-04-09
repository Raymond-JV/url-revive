import argparse
import sys
from argparse import FileType
from urllib.parse import urlparse, urlunparse
from url_revive.config import settings

ascii_art = r"""
 _   _ ___ _      ___         _
| | | | _ \ |    | _ \_____ _(_)_ _____
| |_| |   / |__  |   / -_) V / \ V / -_)
 \___/|_|_\____| |_|_\___|\_/|_|\_/\___|
"""

def get_scheme(url):
    parsed_url = urlparse(url)
    return parsed_url.scheme

def replace_scheme(url, new_scheme='https'):
    parsed_url = urlparse(url)
    if not get_scheme(url):
        return f'{new_scheme}://{url}'
    new_url = parsed_url._replace(scheme=new_scheme)
    return urlunparse(new_url)

def parse_urls(args):
    urls = []
    if args.url:
        urls.append(args.url)
    elif not args.file.isatty():
        urls.extend([line.strip() for line in args.file])
    for i, url in enumerate(urls):
        if not get_scheme(url):
            urls[i] = replace_scheme(urls[i], 'https')
    return urls

def add_input_options(parser):
    input_group = parser.add_argument_group('INPUT')
    input_group.add_argument(
        '-u', '--url', type=str, help='Fetch snapshots for single URL'
    )
    input_group.add_argument(
        '-f',
        '--file',
        type=FileType('r'),
        default='-',
        nargs='?',
        help='Read multiple URLs from file',
    )

def add_filter_options(parser):
    filter_group = parser.add_argument_group('FILTER')
    filter_group.add_argument(
        '-l',
        '--limit',
        type=int,
        default=settings.NETWORK.DEFAULT_FETCH_LIMIT,
        help='Limit number of snapshots fetched per URL',
    )
    filter_group.add_argument(
        '-mc',
        '--match-codes',
        type=str,
        help='Status codes to match -> -mc 200,302,404',
    )
        
def add_general_options(parser):
    general_group = parser.add_argument_group('GENERAL')
    general_group.add_argument(
        '-d',
        '--dump',
        action='store_true',
        help='Print source code dump from snapshots',
    )
    general_group.add_argument(
        '-nc',
        '--no-color',
        action='store_true',
        default=False,
        help='Do not color output',
    )
    general_group.add_argument(
        '-m',
        '--memento',
        action='store_true',
        help='Fetch snapshots from multiple archives with the Memento API',
    )
    general_group.add_argument(
        '-r',
        '--raw',
        action='store_true',
        default=False,
        help='Exclude wayback metadata from snapshots',
    )
    general_group.add_argument(
        '-s',
        '--silent',
        action='store_true',
        help='Only show snapshots or source code dumps',
    )
    general_group.add_argument(
        '--unique',
        action='store_true',
        help='Exclude duplicate URLs',
    )

def parse_args():
    parser = argparse.ArgumentParser()
    add_input_options(parser)
    add_general_options(parser)
    add_filter_options(parser)

    args = parser.parse_args()
    if not args.silent:
        print(ascii_art, file=sys.stderr)
    if args.match_codes:
        args.match_codes = args.match_codes.split(',')
    args.urls = parse_urls(args)
    return args

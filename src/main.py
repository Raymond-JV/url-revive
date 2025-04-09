#!/usr/bin/env python3
import argparse
import fileinput
import logging
import time
import requests
import json
from argparse import FileType 
from dynaconf import settings
from functools import wraps
from urllib.parse import urlparse, urlunparse
from ratelimit import limits, sleep_and_retry
from ratelimit.exception import RateLimitException
from requests.exceptions import ConnectionError, ConnectTimeout
from typing import List

def get_request_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            url = args[0] 
            return func(*args, **kwargs)
        except ConnectionError as e:
            logging.info(f'Failed connecting to {url}')
        except ConnectTimeout as e:
            logging.info(f'Connection to {url} timed out')
        except RateLimitException as e:
            sleep_duration = 10
            logging.info(f'Rate limit encountered, sleeping for {sleep_duration} seconds')
            time.sleep(sleep_duration)
        except Exception as e:
            logging.error(f'Unhandled exception {e}')
    return wrapper

@get_request_handler
def dump_snapshot(url):
    response = requests.get(url, timeout=default_timeout)
    response.raise_for_status()  
    return response.text
    
@get_request_handler
def query_url(url, limit, match_codes):
    params = dict(output='json', url=url, limit=limit)
    if match_codes is not None:
        mc_key = 'filter'
        mc_value = f'statuscode:({"|".join(match_codes)})'
        params[mc_key] = mc_value
    logging.info(f'Fetching record(s) for {url}')
    default_timeout = (settings.CONNECT_TIMEOUT, settings.READ_TIMEOUT)
    response = requests.get(url=settings.ARCHIVES_CDX_API, params=params, timeout=default_timeout)
    response.raise_for_status()  
    data = response.json()
    json_data = json_array_to_json(data)
    return json_data

def parse_snapshot(record, raw = True):
    record_timestamp = record['timestamp']
    if raw:
        record_timestamp += 'id_'
    return f'{settings.ARCHIVES_WEB_API}/{record_timestamp}/{record["original"]}'

def query_batch(urls, limit, match_codes=None):
    for url in urls:
        record = query_url(url, limit, match_codes)
        if record:
            yield record

def json_array_to_json(json_array):
    if not json_array:
        return []
    keys = json_array[0]
    rows = json_array[1:]
    return [dict(zip(keys, row)) for row in rows]

def set_scheme(url, new_scheme="https"):
    parsed_url = urlparse(url)
    new_url = parsed_url._replace(scheme=new_scheme)
    return urlunparse(new_url)

def get_scheme(url):
    parsed_url = urlparse(url)
    return parsed_url.scheme

def query_memento(url):
    fmt_url = f'{settings.MEMENTO_API}/{url}'
    response = requests.get(url=fmt_url)
    response.raise_for_status()
    return response.json()

def extract_archives(timemaps):
    archives = []
    for timemap in timemaps['timemap_index']:
        archives.append(timemap['uri'])
    return archives

def find_active_archives(urls):
    active_archives = set()
    try:
        for url in urls:
            timemaps = query_memento(url)
            archives = extract_archives(timemaps)
            http_url = set_scheme(url, 'http')
            active_archives.update([archive.replace(http_url, '') for archive in archives])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
    finally:
        return active_archives

def parse_urls(args):
    urls = []
    if args.url:
        urls.append(args.url)
    elif not args.file.isatty():
        urls.extend([line.strip() for line in args.file])
    for i,url in enumerate(urls):
        if not get_scheme(url):
            urls[i] = f'https://{url}'
    return urls

def parse_args():
    parser = argparse.ArgumentParser(description='URL Revive')
    parser.add_argument('-u', '--url', type=str, help='Fetch snapshot(s) for single URL')
    parser.add_argument('-f', '--file', type=FileType('r'), default='-', nargs='?', help='Fetch snapshots for multiple URLS in file')
    parser.add_argument('-l', '--limit', type=int, default=settings.DEFAULT_FETCH_LIMIT, help='Limit number of snapshots fetched per URL')
    parser.add_argument('-j', '--json', action='store_true', help='Return as JSON')
    parser.add_argument('-d', '--dump', action='store_true', help='Include dump of source code from responses')
    parser.add_argument('-m', '--memento', action='store_true', help='Fetch snapshots from multiple archives with the Memento api')
    parser.add_argument('-mc', '--match-codes', type=str, help='Status codes to match -> -mc 200,302,404')
    args = parser.parse_args()
    if args.match_codes:
        args.match_codes = args.match_codes.split(',') 
    return args 
    
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    args = parse_args()
    urls = parse_urls(args)
    if args.memento:
        archives = find_active_archives(urls)
        print('\n'.join(archives))
        return
    records = query_batch(urls, args.limit, args.match_codes)
    for record in records:
        for snapshot in record:
            status_code = snapshot['statuscode']
            url = parse_snapshot(snapshot)
            if args.dump:
                source = dump_snapshot(url)
                print(source)
            else:
                print(f'{url} [{status_code}]')

if __name__ == "__main__":
    main()


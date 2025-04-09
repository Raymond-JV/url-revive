import json
import logging
import sys
from dataclasses import dataclass
from enum import Enum
from url_revive.config import settings
from url_revive.networking import RequestThrottler

class ArchiveFormat(Enum):
    CSV = 'csv'
    JSON = 'json'
    JSONL = 'jsonl'
    JSON_CSV = 'json_csv'

@dataclass
class Snapshot:
    url: str
    status: int

def json_csv_to_json(json_array):
    if not json_array:
        return []
    keys = json_array[0]
    rows = json_array[1:]
    return [dict(zip(keys, row)) for row in rows if row]

def format_data_to_json(data, output_format):
    match output_format:
        case ArchiveFormat.CSV:
            data = data.json()
            data = json_csv_to_json(data)
        case ArchiveFormat.JSON:
            data = json.loads(data.text) 
        case ArchiveFormat.JSONL:
            data = data.text.split('\n')
            data = [json.loads(entry) for entry in data if entry]
    return data

def parse_snapshot(record, web_archive, raw=True):
    record_timestamp = record["timestamp"]
    if raw:
        record_timestamp += "id_"
    return f'{web_archive}/{record_timestamp}/{record["original"]}'

def fetch_memento_snapshots(url, limit, match_codes):
    request_throttler = RequestThrottler(1)
    for archive in settings.memento.archives:
        if not archive.ENABLED:
            continue
        logging.info(f'Sending query to archive - {archive.name}')
        memento_url = f'{archive.HOST}/{settings.memento.JSON}/{url}'
        response = request_throttler.safe_get(memento_url)
        output_type = ArchiveFormat(archive.OUTPUT_FORMAT)
        try:
            json_data = format_data_to_json(response, output_type)
        except Exception as e:  
            logging.error(f'Failed to parse response from archive, error - {e}')
            yield []
        snapshots = []
        for entry in json_data:
            timestamp = entry['timestamp']
            snapshot_url = f'{archive.host}/{timestamp}/{url}'
            snapshot = Snapshot(snapshot_url, entry[archive.status_key])
            snapshots.append(snapshot)
        if match_codes:
            snapshots = [snap for snap in snapshots if snap.status in match_codes]
        yield snapshots[:limit]

def fetch_cdx_snapshots(url, limit, match_codes, raw=False, unique=False):
    request_throttler = RequestThrottler(1)
    params = { 'output': 'json', 'url':url, 'limit':limit }
    if unique:
        params['collapse'] = 'urlkey'
    if match_codes is not None:
        mc_key = 'filter'
        mc_value = f'statuscode:({"|".join(match_codes)})'
        params[mc_key] = mc_value
    response = request_throttler.safe_get(
        url=settings.WAYBACK.API_CDX, params=params
    )
    if not response:
        logging.error('Request to Wayback failed')
        return []
    try:
        data = response.json()
        json_data = json_csv_to_json(data)
    except Exception as e:  
        logging.error('Failed to parse response from wayback archive')
        return []
    snapshots = []
    for entry in json_data:
        snapshot_url = parse_snapshot(entry, settings.wayback.api_web, raw=raw) 
        snapshot = Snapshot(snapshot_url, entry[settings.wayback.status_key])
        snapshots.append(snapshot)
    yield snapshots

def main():
    url = sys.argv[1]
    mc = ['200']
    snapshots = fetch_cdx_snapshots(url, 1, mc)
    print(snapshots)

if __name__=='__main__':
    main()

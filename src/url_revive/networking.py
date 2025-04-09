import logging
import requests
import sys
from multipledispatch import dispatch
from pyrate_limiter import Duration, Rate, Limiter, BucketFullException, LimiterDelayException
from url_revive.config import settings

@dispatch(str)
def safe_get(url, params=None):
    default_timeout = (settings.NETWORK.CONNECT_TIMEOUT, settings.NETWORK.READ_TIMEOUT)
    try:
        response = requests.get(url, params=params, timeout=default_timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        logging.error(f'HTTP Error: {e}')
    except requests.exceptions.ConnectionError:
        logging.error(f'Error connecting to {url}')
    except requests.exceptions.Timeout:
        logging.error(f'Connection to {url} timed out')
    except requests.exceptions.RequestException as e:
        logging.error(f'Unhandled RequestException {e}')

@dispatch(list,int)
def safe_get(urls, throttle_rate):
    rate_limit = Rate(1, Duration.SECOND * throttle_rate)
    limiter = Limiter(rate_limit, max_delay=Duration.MINUTE) 
    for url in urls:
        try:
            limiter.try_acquire(url)  
            yield safe_get(url)
        except BucketFullException as e:
            logging.error(f'Rate limit exceeded for {url}: {e}')
        except LimiterDelayException:
            logging.error(f"Delay exceeded for {url} aborting...")

class RequestThrottler:
    def __init__(self, throttle_rate):
        self.rate_limit = Rate(1, Duration.SECOND * throttle_rate)
        self.limiter = Limiter(self.rate_limit, max_delay=Duration.MINUTE) 

    def safe_get(self, url, params=None):
        try:
            self.limiter.try_acquire(url)  
            return safe_get(url, params=params)
        except BucketFullException as e:
            logging.error(f'Rate limit exceeded for {url}: {e}')
        except LimiterDelayException:
            logging.error(f"Delay exceeded for {url} aborting...")

def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    url = sys.argv[1]
    count = int(sys.argv[2])
    urls = [url] * count
    for rsp in safe_get(urls, settings.WAYBACK_API_LIMIT):
        logging.info(rsp)

if __name__=='__main__':
    main()

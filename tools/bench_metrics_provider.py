#!/usr/bin/env python3

from prometheus_client import start_http_server, Histogram, Summary, Enum, Gauge
import subprocess
import psutil
import time
import yaml
import json

import urllib.error
import urllib.parse
import urllib.request

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
cpu_percent = Gauge('cpu_percent', 'CPU %')
vmem_percent = Gauge('vmem_percent', "Virtual memory %")
smem_percent = Gauge('smem_percent', "Swap memory %")
scrape_duration = Gauge('scrape_duration', 'Scrape duration')
scrape_duration_percent = Gauge('scrape_duration_percent', 'Scrape duration %')

prom_scraped_avalanche_successfully = Gauge(
    'prom_scraped_avalanche_successfully',
    'Prom scraped avalanche successfully')


def get_stdout(args: list):
    return subprocess.run(args, stdout=subprocess.PIPE).stdout.decode('utf-8')


def get_json_from_url(url: str, timeout: float = 2.0) -> dict:
    """Send a GET request with a timeout.

    Args:
        url: target url to GET from
        timeout: duration in seconds after which to return, regardless the result

    Raises:
        AlertmanagerBadResponse: If no response or invalid response, regardless the reason.
    """
    try:
        response = urllib.request.urlopen(url, data=None, timeout=timeout)
        if response.code == 200 and response.reason == "OK":
            return json.loads(response.read())
    except (ValueError, urllib.error.HTTPError, urllib.error.URLError):
        return {}


def get_prom_address(unit="prometheus/0"):
    unit_info = yaml.safe_load(get_stdout(['juju', 'show-unit', unit]))
    return unit_info[unit]["address"]


def get_scrape_duration():
    targets_url = f"http://{get_prom_address()}:9090/api/v1/targets"
    targets_info = get_json_from_url(targets_url)  # json.loads(get_stdout(["curl", "--no-progress-meter", targets_url]))
    ours = list(filter(lambda target: target["discoveredLabels"]["__address__"] == "192.168.1.101:9001", targets_info["data"]["activeTargets"]))
    prom_scraped_avalanche_successfully.set(int(ours[0]["health"] == "up"))
    return ours[0]["lastScrapeDuration"]


def get_scrape_interval() -> int:
    config_url = f"http://{get_prom_address()}:9090/api/v1/status/config"
    config_info = get_json_from_url(config_url)  # json.loads(get_stdout(["curl", "--no-progress-meter", config_url]))
    config_info = yaml.safe_load(config_info["data"]["yaml"])
    ours = list(
        filter(lambda scrape_config: scrape_config["static_configs"][0]["targets"] == ["192.168.1.101:9001"],
               config_info["scrape_configs"]))
    as_str = ours[0]["scrape_interval"]
    as_int = int(as_str[:-1])  # assuming it is always "10s" etc.
    return as_int


def process_sys_metrics():
    cpu_percent.set(psutil.cpu_percent())
    vmem_percent.set(psutil.virtual_memory().percent)
    smem_percent.set(psutil.swap_memory().percent)


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(8000)

    while True:
        print("Trying to comm with prom...")
        try:
            scrape_interval = get_scrape_interval()
            print("Success.")
            break
        except:
            time.sleep(2)

    while True:
        process_sys_metrics()
        if not int(time.time()) % scrape_interval:
            try:
                with REQUEST_TIME.time():
                    sd = get_scrape_duration()
                    scrape_interval = get_scrape_interval()
                    scrape_duration.set(sd)
                    scrape_duration_percent.set(sd/scrape_interval * 100)
            except:
                prom_scraped_avalanche_successfully.set(0)

        time.sleep(1)

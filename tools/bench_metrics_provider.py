from prometheus_client import start_http_server, Histogram, Summary
import subprocess
import time
import yaml
import json

# Create a metric to track time spent and requests made.
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')

scrape_duration = Histogram(
    'scrape_duration',
    'Scrape duration',
    buckets=(.01, .05, .1, .5, 1.0, 2.5, 5.0, 7.5, 10.0, 20.0, float("inf"))
)


def get_stdout(args: list):
    return subprocess.run(args, stdout=subprocess.PIPE).stdout.decode('utf-8')


def get_prom_address(unit="prometheus/0"):
    unit_info = yaml.safe_load(get_stdout(['juju', 'show-unit', unit]))
    return unit_info[unit]["address"]


def get_scrape_duration():
    targets_url = f"http://{get_prom_address()}:9090/api/v1/targets"
    tagets_info = json.loads(get_stdout(["curl", "--no-progress-meter", targets_url]))
    ours = list(filter(lambda target: target["discoveredLabels"]["__address__"] == "192.168.1.101:9001", tagets_info["data"]["activeTargets"]))
    return ours[0]["lastScrapeDuration"]


# Decorate function with metric.
@REQUEST_TIME.time()
def process_metrics():
    scrape_duration.observe(get_scrape_duration())


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(8000)
    # Generate some requests.
    while True:
        process_metrics()
        time.sleep(10.0)

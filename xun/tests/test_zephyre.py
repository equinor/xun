from .helpers import capture_stdout
from .helpers import tmpwd
from camille.util import utcdate
from pathlib import Path
from pkg_resources import resource_stream
from unittest.mock import patch
from xun import cli
from xun import filename_from_args
from xun.zephyre import schema as load_schema
import datetime
import fastavro
import hashlib
import json
import pytest  # noqa: F401


schema = load_schema()
date_fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
http_response = b"""
[
    { "value": 0.0
    , "time": "2030-01-01T00:00:00.000000"
    , "quality": 192
    },
    { "value": -0.8660254038
    , "time": "2030-01-01T00:00:10.000000"
    , "quality": 192
    },
    { "value": -0.8660254038
    , "time": "2030-01-01T00:00:20.000000"
    , "quality": 192
    }
]
"""
reference = [
    {'time': 1893456000000000000, 'value': '0.0'},
    {'time': 1893456010000000000, 'value': '-0.8660254038'},
    {'time': 1893456020000000000, 'value': '-0.8660254038'}
]


def parse_date(str): return utcdate(datetime.datetime.strptime(str, date_fmt))


class MockResponse:
    def __init__(self, tag, start_date, end_date, status_code):
        self.json_bytes = http_response
        self.status_code = status_code

    def raise_for_status(self):
        if (self.status_code != 200):
            raise requests.HTTPError('Mock error')

    def iter_content(self, chunk_size):
        for i in range(0, len(self.json_bytes), chunk_size):
            yield self.json_bytes[i:i + chunk_size]

# This method will be used by the mock to replace requests.get
def requests_get_mock(url, params={}, headers={}, stream=False):
    assert headers['Authorization'] == 'Bearer token'
    assert stream
    assert 'measurementName' in params
    assert 'start' in params
    assert 'end' in params

    start = parse_date(params['start'])
    end = parse_date(params['end'])
    tag = params['measurementName']

    return MockResponse(tag, start, end, 200)


def test_zephyre(tmpwd):
    argv = ['tag', '2030-01-01', '2030-01-02']
    args = cli.parser.parse_args(['zephyre', *argv])

    with patch(
        'camille.source.zephyre.Zephyre._get_token', return_value='token'
    ), patch(
        'camille.source.zephyre.requests.get',
        side_effect=requests_get_mock,
    ):
        args.func(args)

    expected_filename = filename_from_args(args,
                                           prefix='zephyre.',
                                           postfix='.avro')

    with open(expected_filename, 'rb') as f:
        avro_reader = fastavro.reader(f, reader_schema=schema)
        result = list(avro_reader)

    assert result == reference


def test_zephyre_out_schema():
    argv = ['zephyre', '--out-schema']

    with capture_stdout() as stdout, pytest.raises(SystemExit) as exit:
        args = cli.parser.parse_args(argv)

    assert exit.value.code == 0

    captured_schema = json.loads(stdout.read())
    assert captured_schema == schema

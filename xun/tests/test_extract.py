from .. import cli
from xun import ExtractError
from pathlib import Path
import pytest  # noqa: F401
import argparse
import fastavro
import json
import struct


def test_missing_arguments():
    try:
        cli.parser.parse_args([ 'extract', 'iff'])
    except SystemExit as e:
        assert e.code == 2


def test_invalid_format():
    with pytest.raises(ValueError) as argErr:
        cli.valid_format('<<025f!f<bbbb=17d306fb6')
        assert 'Not a valid format' in str(argErr.value)


def test_valid_format():
    s = 'i24fi'
    assert s == cli.valid_format(s)


def test_invalid_path():
    with pytest.raises(ValueError) as argErr:
        cli.valid_file_path('file_do_not_exist.bin')
        assert 'Not a valid path to a file' in str(argErr.value)


def test_invalid_bin_size():
    with pytest.raises(ExtractError) as ex_err:
        set_xun_sima_root_args = cli.parser.parse_args([ 
            'extract',
            'i5fi', 
            '-bi', 'xun/tests/test_data/data.bin',
            '-o', 'xun/tests/test_data/out.avro'])
        set_xun_sima_root_args.func(set_xun_sima_root_args)


def test_get_schema_only():
    set_xun_sima_root_args = cli.parser.parse_args([ 
        'extract',
        'i2fi', 
        '--out-schema',
        '-o', 'xun/tests/test_data/out.json'])
    set_xun_sima_root_args.func(set_xun_sima_root_args)

    schema_input = {
        'type': 'record',
        'name': 'sima_bin',
        'fields': [
            {'name': 'col_0', 'type': 'int'},
            {'name': 'col_1', 'type': 'float'},
            {'name': 'col_2', 'type': 'float'},
            {'name': 'col_3', 'type': 'int'}
            ]
        }
    
    schema_json = {}
    with open('xun/tests/test_data/out.json', 'rb') as oj:
        schema_json = json.load(oj)
    
    assert schema_input == schema_json


def test_extract():
    set_xun_sima_root_args = cli.parser.parse_args([ 
        'extract',
        'i24fi', 
        '-bi', 'xun/tests/test_data/data.bin',
        '-o', 'xun/tests/test_data/out.avro'])
    set_xun_sima_root_args.func(set_xun_sima_root_args)

    test_data = {}
    with open('xun/tests/test_data/data.bin', 'rb') as db:
        td = struct.unpack('i24fi', db.read())
        test_data = dict(('col_{}'.format(i), v) for (i,v) in enumerate(td))

    avro_data = {}
    with open('xun/tests/test_data/out.avro', 'rb') as oa:
        for record in fastavro.reader(oa):
            avro_data = record

    assert avro_data == pytest.approx(test_data)


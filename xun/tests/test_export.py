from .. import cli
from .. import cli_helpers
from .helpers import capture_stdout
from xun import ExportError
import pytest
import fastavro
import json
import struct


def test_invalid_format():
    with pytest.raises(ValueError) as argErr:
        cli_helpers.struct_fmt('<<025f!f<bbbb=17d306fb6')
        assert 'Not a valid format' in str(argErr.value)


def test_valid_format():
    s = 'i24fi'
    assert s == cli_helpers.struct_fmt(s)


def test_invalid_bin_size():
    with pytest.raises(ExportError):
        set_xun_sima_root_args = cli.parser.parse_args([
            'sima-export',
            'i5fi',
            'xun/tests/test_data/data.bin',
            '-o', 'xun/tests/test_data/out.avro'])
        set_xun_sima_root_args.func(set_xun_sima_root_args)


def test_get_schema_only():
    with capture_stdout() as stdout, pytest.raises(SystemExit):
        cli.parser.parse_args([
            'sima-export',
            'i2fi',
            '--out-schema'])

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

    schema_json = json.loads(stdout.read())

    assert schema_input == schema_json


def test_export(tmpwd):
    ref_path = tmpwd.old / 'xun/tests/test_data/data.bin'

    set_xun_sima_root_args = cli.parser.parse_args([
        'sima-export',
        'i24fi',
        str(ref_path),
        '-o', 'out.avro'])
    set_xun_sima_root_args.func(set_xun_sima_root_args)

    test_data = {}
    with open(str(ref_path), 'rb') as db:
        td = struct.unpack('i24fi', db.read())
        test_data = dict(('col_{}'.format(i), v) for (i,v) in enumerate(td))

    avro_data = {}
    with open('out.avro', 'rb') as oa:
        for record in fastavro.reader(oa):
            avro_data = record

    assert avro_data == pytest.approx(test_data)

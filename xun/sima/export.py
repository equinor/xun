from .. import filename_from_args
from xun import ExportError
from pathlib import Path
import struct
import fastavro
import re
import json
import logging


char_to_word = {
    "?" : "boolean",
    "i" : "int",
    "l" : "long",
    "f" : "float",
    "d" : "double",
    "b" : "bytes",
    "c" : "bytes",
    "s" : "string",
    "p" : "string"
}


def generate_field(index, format_char):
    return {
        "name": "col_{}".format(index),
        "type": char_to_word[format_char]
    }


def process_part(format_part):
    part_str = format_part[0]
    if len(part_str) == 1:
        return part_str
    else:
        multi = int(part_str[:-1])
        return part_str[-1] * multi


def generate_avro_schema(format_arr):
    format_str = ''.join([process_part(part) for part in format_arr])
    return {
        "type": "record",
        "name": "sima_bin",
        "fields": [generate_field(i, ch) for (i,ch) in enumerate(format_str)]
    }


def schema(format_in):
    reg = re.compile(r'(([1-9][0-9]*)?[cb\?ilfdsp])')
    format_str = format_in.replace('<', '').replace('>', '')
    format_str = format_str.replace('!', '').replace('@', '')
    matches = reg.findall(format_str)
    return generate_avro_schema(matches)


def read_in_chunks(file_object, chunk_size):
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data


def main(args):
    schema_row_size = struct.calcsize(args.format)
    parsed_schema = fastavro.parse_schema(schema(args.format))

    file_path = Path(args.bin_input)
    file_size = file_path.stat().st_size

    out_filename = (
        args.output if args.output
        else filename_from_args(args, prefix='sima.exported.', postfix='.avro')
    )

    if file_size % schema_row_size != 0:
        msg = 'Format {} does not fit into file {}'.format(
            args.format,
            args.bin_input
        )
        raise ExportError(msg)

    with open(str(file_path), 'rb') as binf, open(out_filename, 'wb') as avrf:
        records = (
            {
                "col_{}".format(i): v
                for i, v in enumerate(struct.unpack(args.format, piece))
            }
            for piece in read_in_chunks(binf, schema_row_size)
        )
        fastavro.writer(
            avrf,
            parsed_schema,
            records,
            codec='deflate',
            codec_compression_level=4
        )

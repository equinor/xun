from xun import ExtractError
from pathlib import Path
import struct
import fastavro
import re
import json
import logging


__char_to_word = {
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


def __generate_field(index, format_char):
    return {
        "name" : "col_{}".format(index),
        "type" : __char_to_word[format_char]
    }


def __process_part(format_part):
    part_str = format_part[0]
    if isinstance(part_str, str):
        if len(part_str) == 1:
            return part_str
        else:
            multi = int(part_str[:-1])
            return part_str[-1] * multi
    return ''


def __generate_avro_schema(format_arr):
    format_str = ''.join([__process_part(part) for part in format_arr])
    return {
        "type": "record",
        "name": "sima_bin",
        "fields": [__generate_field(i, ch) for (i,ch) in enumerate(format_str)]
    }


def __get_schema(format_in):
    reg = re.compile(r'(([1-9][0-9]*)?[cb\?ilfdsp])')
    format_str = format_in.replace('<', '').replace('>', '')
    format_str = format_str.replace('!', '').replace('@', '')
    matches = reg.findall(format_str)
    return __generate_avro_schema(matches)


def __read_in_chunks(file_object, chunk_size=1024):
    count = 0
    while True:
        data = file_object.read(chunk_size)
        count += 1
        if not data:
            break
        if count == 2:
            break
        yield data


def cmd_extract(args):
    schema_row_size = struct.calcsize(args.format)
    schema = __get_schema(args.format)
    parsed_schema = fastavro.parse_schema(schema)

    if args.out_schema:
        with open(args.output, 'w') as schema_out:
            json.dump(schema, schema_out)
    else:
        file_path = Path(args.bin_input)

        file_size = file_path.stat().st_size

        if file_size % schema_row_size != 0:
            msg = 'Format {} does not fit into file {}'.format(
                args.format,
                args.bin_input
            )
            raise ExtractError(msg)

        records = []
        with open(str(file_path), 'rb') as binf:
            for piece in __read_in_chunks(binf, schema_row_size):
                data = enumerate(struct.unpack(args.format, piece))
                records.append(dict(("col_{}".format(i), v) for (i,v) in data))
        with open(args.output, 'wb') as avrf:
            fastavro.writer(
                avrf, 
                parsed_schema, 
                records, 
                codec='deflate', 
                codec_compression_level=4
            )
    




from .. import filename_from_args
from ..memoized import memoized
from camille.source import Zephyre
import fastavro
import json
import numpy as np
import pkg_resources


def main(args):
    z = Zephyre()
    series = z(args.measurement_name, args.start_time, args.end_time)
    series.index = series.index.astype(np.int64)

    records = series.to_frame().to_records()
    avro_records = ({'time': t, 'value': str(v)} for t, v in records)

    filename = (
        args.output if args.output
        else filename_from_args(args, prefix='zephyre.', postfix='.avro')
    )

    with open(filename, 'wb') as f:
        fastavro.writer(f, schema(), avro_records)


@memoized
def schema():
    schema_str = pkg_resources.resource_string('xun', 'zephyre/zephyre.avsc')
    schema_dict = json.loads(schema_str)
    return schema_dict

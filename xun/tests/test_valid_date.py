from .. import cli
from camille.util import utcdate


def test_valid_date():
        reference = [
            ('2030-02-02', utcdate(year=2030, month=2, day=2)),
            ('2030-02-02T01:00:00', utcdate(year=2030, month=2, day=2, hour=1)),
            (
                '2030-02-02T01:00:00.123456',
                utcdate(year=2030,
                        month=2,
                        day=2,
                        hour=1,
                        minute=0,
                        second=0,
                        microsecond=123456)
            ),
        ]
        for arg, expected in reference:
            args = cli.parser.parse_args(['zephyre', 'tag', arg, arg])
            assert args.start_time == expected
            assert args.end_time == expected

from .functor import IsoFunctor
from .functor import _internal_type
from io import StringIO
import pandas as pd


@_internal_type(pd.DataFrame)
class FrameFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, json_str):
            buffer = StringIO(json_str)
            series = pd.read_json(buffer, orient='split')
            return series

        def __invert__(cls):
            return SeriesFunctor

    def __call__(cls, series):
        buffer = StringIO()
        series.to_json(buffer,
                       orient='split',
                       date_format='iso',
                       date_unit='ns')
        return buffer.getvalue()

    def __invert__(cls):
        return cls._Inverse


@_internal_type(pd.Series)
class SeriesFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, json_str):
            buffer = StringIO(json_str)
            series = pd.read_json(buffer, orient='split', typ='series')
            return series

        def __invert__(cls):
            return SeriesFunctor

    def __call__(cls, series):
        buffer = StringIO()
        series.to_json(buffer,
                       orient='split',
                       date_format='iso',
                       date_unit='ns')
        return buffer.getvalue()

    def __invert__(cls):
        return cls._Inverse

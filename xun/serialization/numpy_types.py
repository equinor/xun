from .functor import IsoFunctor
from .functor import _internal_type
from base64 import b64decode
from base64 import b64encode
from io import BytesIO
import numpy as np


@_internal_type(np.ndarray, *np.typeDict.values())
class NumpyFunctor(metaclass=IsoFunctor):
    class _Inverse(metaclass=IsoFunctor):
        def __call__(cls, b64):
            binary = b64decode(b64.encode())
            buffer = BytesIO(binary)

            # allow_pickle must be set to False, True allows RCE
            # https://nvd.nist.gov/vuln/detail/CVE-2019-6446
            value = np.load(buffer, allow_pickle=False)

            if value.ndim == 0:
                # Numpy load returns a 0-dimensional ndarray when loading
                # scalars. value.take(0) retrieves the stored scalar.
                value = value.take(0)

            return value

        def __invert__(cls):
            return NumpyFunctor

    def __call__(cls, numpy_val):
        buffer = BytesIO()

        # allow_pickle must be set to False, True allows RCE
        # https://nvd.nist.gov/vuln/detail/CVE-2019-6446
        np.save(buffer, numpy_val, allow_pickle=False)

        return b64encode(buffer.getvalue()).decode()

    def __invert__(cls):
        return cls._Inverse

from .helpers import run_in_process
import xun


def test_xun_result_references():
    @xun.function()
    def return_reference():
        data = b'hello world!\n'
        return xun.Reference(data)

    @xun.function()
    def use_reference():
        with ...:
            ref = return_reference()
        assert ref.value == b'hello world!\n'

    run_in_process(use_reference.blueprint())

from textwrap import indent


class ComputeError(Exception):
    pass


class CopyError(Exception):
    def __init__(self, callnode, msg=None):
        self.callnode = callnode
        if msg is None:
            msg = 'Cannot copy {}'
        super().__init__(msg.format(callnode))

    @property
    def function_name(self):
        return self.callnode.function_name

    @property
    def args(self):
        return self.callnode.args

    @property
    def kwargs(self):
        return self.callnode.kwargs


class FunctionDefNotFoundError(Exception):
    pass


class FunctionError(Exception):
    def __init__(self, function_name, source, original=None):
        msg = f'failed to run function {function_name}'
        msg += '\ncode:\n\n'
        msg += indent(source, ' ' * 4)

        if original is not None:
            msg += '\n\ngenerated from\n\n'
            msg += indent(original, ' ' * 4)

        super().__init__(msg)


class NotDAGError(Exception):
    pass


class XunInterfaceError(Exception):
    pass


class XunSyntaxError(Exception):
    pass

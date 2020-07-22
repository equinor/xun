from abc import ABC
from abc import abstractmethod


class Driver(ABC):
    """Driver

    Drivers are the classes that have the responsibility of executing programs.
    This includes scheduling the calls of the call graph and managing any
    concurency.
    """
    @abstractmethod
    def exec(self, program):
        pass

    def __call__(self, program):
        return self.exec(program)

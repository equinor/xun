from abc import ABC
from abc import abstractmethod


class Driver(ABC):
    @abstractmethod
    def exec(self, program):
        pass

    def __call__(self, program):
        return self.exec(program)

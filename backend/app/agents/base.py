"""
filename: base.py
description: Shared Agent abstraction. Subclasses implement run().
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from abc import ABC, abstractmethod
from typing import Any


class Agent(ABC):
    name: str = "base"

    @abstractmethod
    async def run(self, payload: dict) -> Any:
        raise NotImplementedError

from enum import Enum

from pydantic import BaseModel


class Ecosystem(str, Enum):
    NPM = "npm"
    PYPI = "pypi"
    MAVEN = "maven"
    UNKNOWN = "unknown"


class Package(BaseModel):
    name: str
    version: str
    ecosystem: Ecosystem
    direct: bool = True
    parents: list[str] = []


class DependencyGraph(BaseModel):
    packages: list[Package]
    ecosystem_counts: dict[str, int]
    direct_count: int
    transitive_count: int

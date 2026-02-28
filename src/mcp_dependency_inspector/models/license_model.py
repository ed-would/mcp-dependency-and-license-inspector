from enum import Enum

from pydantic import BaseModel

from .package import Package


class LicenseCategory(str, Enum):
    PERMISSIVE = "permissive"
    COPYLEFT = "copyleft"
    UNKNOWN = "unknown"
    MULTIPLE = "multiple"


class LicenseInfo(BaseModel):
    spdx_id: str | None = None
    name: str
    category: LicenseCategory
    is_copyleft: bool = False
    is_unknown: bool = False
    is_multiple: bool = False


class PackageLicense(BaseModel):
    package: Package
    license: LicenseInfo

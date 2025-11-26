"""
Exceptions for the EBS Manager module.
"""


class VolumeNotFoundError(ValueError):
    """Raised when a volume is not found in any region."""

    def __init__(self, volume_id: str):
        super().__init__(f"Volume {volume_id} not found in any region")

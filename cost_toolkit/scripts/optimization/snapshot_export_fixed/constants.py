"""Constants and exceptions for snapshot export operations."""

# All timing and threshold constants derived from AWS documentation and real-world testing
EXPORT_STATUS_CHECK_INTERVAL_SECONDS = 60
EXPORT_MAX_DURATION_HOURS = 8

S3_STABILITY_CHECK_MINUTES = 10
S3_STABILITY_CHECK_INTERVAL_MINUTES = 5
S3_FAST_CHECK_MINUTES = 2
S3_FAST_CHECK_INTERVAL_MINUTES = 1

VMDK_MIN_COMPRESSION_RATIO = 0.1
VMDK_MAX_EXPANSION_RATIO = 1.2

MAX_CONSECUTIVE_API_ERRORS = 3

S3_STANDARD_COST_PER_GB_MONTHLY = 0.023


class ExportTaskDeletedException(Exception):
    """Raised when AWS export task is deleted during processing"""


class ExportTaskFailedException(Exception):
    """Raised when AWS export task fails"""


class ExportTaskStuckException(Exception):
    """Raised when export task appears permanently stuck"""


class ExportAPIException(Exception):
    """Raised when too many consecutive API errors occur"""


class S3FileValidationException(Exception):
    """Raised when S3 file validation fails"""


if __name__ == "__main__":
    pass

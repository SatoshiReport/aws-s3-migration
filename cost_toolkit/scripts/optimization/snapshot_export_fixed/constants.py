"""Constants and exceptions for snapshot export operations."""

# All timing and threshold constants derived from AWS documentation and real-world testing
AMI_CREATION_MAX_WAIT_MINUTES = 20
AMI_CREATION_CHECK_INTERVAL_SECONDS = 30

EXPORT_STATUS_CHECK_INTERVAL_SECONDS = 60
EXPORT_MAX_DURATION_HOURS = 8
EXPORT_STUCK_DETECTION_HOURS = 1.0
EXPORT_80_PERCENT_STUCK_DETECTION_MINUTES = 30
EXPORT_S3_CHECK_INTERVAL_MINUTES = 15

S3_STABILITY_CHECK_MINUTES = 10
S3_STABILITY_CHECK_INTERVAL_MINUTES = 5
S3_FAST_CHECK_MINUTES = 2
S3_FAST_CHECK_INTERVAL_MINUTES = 1

VMDK_MIN_COMPRESSION_RATIO = 0.1
VMDK_MAX_EXPANSION_RATIO = 1.2

MAX_CONSECUTIVE_API_ERRORS = 3

EBS_SNAPSHOT_COST_PER_GB_MONTHLY = 0.05
S3_STANDARD_COST_PER_GB_MONTHLY = 0.023


class ExportTaskDeletedException(Exception):
    """Raised when AWS export task is deleted during processing"""


class ExportTaskStuckException(Exception):
    """Raised when export task appears permanently stuck"""


class S3FileValidationException(Exception):
    """Raised when S3 file validation fails"""

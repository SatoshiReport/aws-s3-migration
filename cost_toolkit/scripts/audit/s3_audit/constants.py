"""
Constants for S3 audit.
Storage class pricing and threshold definitions.
"""

# Constants for age thresholds
DAYS_THRESHOLD_IA = 30  # Days threshold for Standard-IA storage class transition
DAYS_THRESHOLD_GLACIER = 90  # Days threshold for Glacier archival transition
DAYS_THRESHOLD_VERY_OLD = 365  # Days threshold for very old objects (1 year)

# S3 storage class pricing per GB/month (US East 1 rates as baseline)
STORAGE_CLASS_PRICING = {
    "STANDARD": 0.023,
    "REDUCED_REDUNDANCY": 0.024,
    "STANDARD_IA": 0.0125,
    "ONEZONE_IA": 0.01,
    "GLACIER": 0.004,
    "DEEP_ARCHIVE": 0.00099,
    "GLACIER_IR": 0.004,
    "INTELLIGENT_TIERING": 0.0125,
    "OUTPOSTS": 0.068,
}

# Request pricing per 1000 requests
REQUEST_PRICING = {
    "PUT_COPY_POST_LIST": 0.0005,  # PUT, COPY, POST, LIST requests per 1000
    "GET_SELECT": 0.0004,  # GET, SELECT requests per 1000
    "LIFECYCLE_TRANSITION": 0.01,  # Lifecycle transition requests per 1000
    "DATA_RETRIEVAL_GLACIER": 0.01,  # Glacier retrieval per 1000
    "DATA_RETRIEVAL_DEEP_ARCHIVE": 0.02,  # Deep Archive retrieval per 1000
}


if __name__ == "__main__":
    pass

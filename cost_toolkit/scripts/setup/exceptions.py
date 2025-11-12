"""Custom exceptions for AWS Route53 setup scripts."""


class HostedZoneNotFoundError(Exception):
    """Raised when no hosted zone is found for a domain"""

    def __init__(self, domain_name):
        super().__init__(f"No hosted zone found for {domain_name}")


class NSRecordsNotFoundError(Exception):
    """Raised when no NS records are found for a domain"""

    def __init__(self, domain_name):
        super().__init__(f"No NS records found for {domain_name}")


class AWSAPIError(Exception):
    """Raised when AWS API encounters an error"""

    def __init__(self, original_error):
        super().__init__(f"AWS API error: {original_error}")


class DNSSetupError(Exception):
    """Raised when DNS setup verification fails"""

    def __init__(self, original_error):
        super().__init__(f"Error verifying DNS setup: {original_error}")


class DNSRecordCreationError(Exception):
    """Raised when DNS record creation fails"""

    def __init__(self, original_error):
        super().__init__(f"Error creating DNS records: {original_error}")


class CertificateInfoError(Exception):
    """Raised when certificate date information is not available"""

    def __init__(self):
        super().__init__("Certificate date information not available")


if __name__ == "__main__":
    pass

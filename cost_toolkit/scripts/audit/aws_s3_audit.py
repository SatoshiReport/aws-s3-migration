#!/usr/bin/env python3
"""
AWS S3 Comprehensive Audit Script
Analyzes S3 buckets, objects, storage classes, costs, and optimization opportunities.

This script now imports from the s3_audit package for modularity.
"""

from cost_toolkit.scripts.audit.s3_audit import audit_s3_comprehensive

if __name__ == "__main__":  # pragma: no cover - script entry point
    audit_s3_comprehensive()

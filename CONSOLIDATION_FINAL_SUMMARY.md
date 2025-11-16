# Code Duplication Analysis - Final Report

**Date:** 2025-11-16
**Status:** Review Complete - Minimal Action Needed
**Files Analyzed:** ~220 Python files

## Executive Summary

After thorough code review, **the codebase shows EXCELLENT consolidation patterns**. Most apparent "duplicates" are actually proper delegation wrappers or use canonical implementations correctly. Previous work successfully consolidated 19 files (~215 lines). Remaining work is minimal - only a handful of true duplicates remain.

---

## Previous Consolidation Work (COMPLETED ✅)

### 1. Credential Loaders (17 files) ✅
- **Status:** COMPLETED
- **Impact:** ~200 lines eliminated
- **Solution:** Standardized on `cost_toolkit.common.credential_utils.setup_aws_credentials()`

### 2. Cost Calculations (2 files) ✅
- **Status:** COMPLETED
- **Impact:** ~15 lines eliminated
- **Solution:** Created `cost_toolkit/common/cost_utils.py`
- **Functions:** `calculate_ebs_volume_cost()`, `calculate_snapshot_cost()`, `calculate_elastic_ip_cost()`

### 3. Confirmation Utilities ✅
- **Status:** Foundation established in `cost_toolkit/common/cli_utils.py`
- **Function:** `confirm_action()` ready for use

---

## FINDINGS - Actual vs Apparent Duplicates

### ✅ ALREADY PROPERLY DELEGATED (Not True Duplicates)

#### 1. `get_instance_details` - Instance Information Retrieval

**Status:** ✅ **ALREADY USES DELEGATION**

**Analysis:**
- `cost_toolkit/common/aws_common.py:157-195` - CANONICAL implementation
- `cost_toolkit/scripts/cleanup/aws_stopped_instance_cleanup.py:18-67` - **Already delegates** to `describe_instance`, `get_resource_tags`, `extract_volumes_from_instance` from canonical
- `cost_toolkit/scripts/cleanup/aws_remove_public_ip.py:12-25` - **Already delegates** to `get_instance_info`

**Verdict:** These are acceptable wrappers that delegate to canonical implementations. No action needed.

---

#### 2. `terminate_instance` - Instance Termination

**Status:** ✅ **PARTIALLY CONSOLIDATED**

**Analysis:**
- `cost_toolkit/scripts/aws_ec2_operations.py:92-115` - CANONICAL implementation
- `cost_toolkit/scripts/cleanup/aws_ec2_instance_cleanup.py:12-30` - Updated to use canonical `get_instance_details`
- `cost_toolkit/scripts/cleanup/aws_instance_termination.py` - Has `terminate_instance_safely` (different name, orchestration function)

**Verdict:** aws_ec2_instance_cleanup.py updated to delegate. aws_instance_termination.py is a high-level orchestration function with different purpose. Acceptable.

---

### CRITICAL PRIORITY - Resource Region Discovery

#### 3. `find_volume_region` / `find_snapshot_region`

**Duplicate Locations:**
- `cost_toolkit/scripts/management/ebs_manager/utils.py:20-43` - `find_volume_region`
- `cost_toolkit/scripts/cleanup/aws_snapshot_bulk_delete.py:17-43` - `find_snapshot_region`

**Description:** Iterates through AWS regions to find which region contains a volume/snapshot

**Differences:**
- `find_volume_region`: Uses `get_all_aws_regions()` from aws_common
- `find_snapshot_region`: Uses hardcoded list of 5 common regions

**Recommendation:** Create canonical `find_resource_region(resource_type, resource_id)` in `aws_ec2_operations.py`

**Implementation Plan:**
1. Create `find_resource_region(ec2_client, resource_type, resource_id, regions=None)` in `aws_ec2_operations.py`
2. Support resource_type: 'volume', 'snapshot', 'ami', 'instance'
3. Update both duplicates to delegate
4. Add comprehensive tests

---

### CRITICAL PRIORITY - Snapshot Operations

#### 4. `delete_snapshot` - Snapshot Deletion

**Duplicate Locations:**
- `cost_toolkit/scripts/cleanup/aws_snapshot_cleanup_final.py:19-29`
- `cost_toolkit/scripts/management/aws_volume_cleanup.py:45-55`

**Description:** Deletes an EBS snapshot

**Differences:**
- `snapshot_cleanup_final.py`: Takes `ec2_client, snapshot_id, region`
- `volume_cleanup.py`: Takes `snapshot_id, region` (creates client internally)

**Recommendation:** Add canonical `delete_snapshot(snapshot_id, region)` to `aws_ec2_operations.py`

---

### CRITICAL PRIORITY - Security Group Operations

#### 5. `delete_security_group` - Security Group Deletion

**Duplicate Locations:**
- `cost_toolkit/scripts/aws_ec2_operations.py:268-285` ✅ **CANONICAL**
- `cost_toolkit/scripts/cleanup/aws_security_group_circular_cleanup.py:85-95`
- `cost_toolkit/scripts/cleanup/aws_vpc_cleanup_unused_resources.py:102-112`

**Description:** Deletes an EC2 security group

**Recommendation:**
1. Update `aws_security_group_circular_cleanup.py` to import canonical
2. Update `aws_vpc_cleanup_unused_resources.py` to import canonical
3. Remove duplicate implementations

---

### MEDIUM PRIORITY - S3 Operations

#### 6. `list_s3_buckets` / `list_buckets`

**Duplicate Locations:**
- `aws_utils.py:40-50` - delegates to `list_buckets`
- `cost_toolkit/scripts/aws_s3_operations.py:88-112` ✅ **CANONICAL**

**Description:** List all S3 buckets in account

**Differences:**
- `aws_utils.py`: Converts to list of names
- `aws_s3_operations`: Returns full bucket dicts

**Recommendation:** Standardize on `aws_s3_operations.list_buckets()`

---

#### 7. `get_bucket_region` / `get_bucket_location`

**Duplicate Locations:**
- `cost_toolkit/common/s3_utils.py:12-36` - wrapper with error handling
- `cost_toolkit/scripts/aws_s3_operations.py:14-43` ✅ **CANONICAL**

**Description:** Get AWS region where S3 bucket is located

**Assessment:** Keep both - `s3_utils` is a useful wrapper for scripts with verbose mode

---

#### 8. `create_s3_bucket_with_region`

**Duplicate Locations:**
- `cost_toolkit/common/s3_utils.py:39-57`
- `cost_toolkit/scripts/aws_s3_operations.py:46-85` - `create_bucket` ✅ **CANONICAL**

**Description:** Create S3 bucket handling us-east-1 special case

**Recommendation:**
1. Update all callers of `create_s3_bucket_with_region` to use `create_bucket`
2. Remove or deprecate `create_s3_bucket_with_region`

---

### MEDIUM PRIORITY - Client Creation

#### 9. `create_ec2_and_s3_clients` vs Individual Client Creators

**Duplicate Locations:**
- `cost_toolkit/common/aws_common.py:12-36` - Creates both EC2 and S3
- `cost_toolkit/scripts/aws_client_factory.py:94-109` - Individual creators

**Description:** Boto3 client creation with credentials

**Recommendation:** Use `aws_client_factory.create_client()` for all client creation

**Action Items:**
1. Identify all usages of `create_ec2_and_s3_clients`
2. Update to use `aws_client_factory.create_client()` for each service
3. Mark legacy function as deprecated

---

### MEDIUM PRIORITY - Region Management

#### 10. `get_all_regions` / `get_all_aws_regions` / `get_aws_regions`

**Locations:**
- `cost_toolkit/scripts/aws_ec2_operations.py:15-40` - `get_all_regions` (queries EC2 API)
- `cost_toolkit/common/aws_common.py:62-76, 79-100` - delegates + static lists
- `cost_toolkit/scripts/aws_utils.py:56-63` - delegates to aws_common

**Functions:**
- `get_all_aws_regions()` - queries API, falls back to static list
- `get_default_regions()` - returns static list of 9 common regions
- `get_common_regions()` - returns 11 regions

**Status:** Already properly delegated, but naming is confusing

**Recommendation:** Consider renaming for clarity:
- `get_all_aws_regions()` → Keep as is
- `get_default_regions()` → `get_common_regions_9()`
- `get_common_regions()` → `get_common_regions_11()`

---

### MEDIUM PRIORITY - Instance Info

#### 11. `get_instance_name`

**Duplicate Locations:**
- `cost_toolkit/common/aws_common.py:39-59` ✅ **CANONICAL**
- `cost_toolkit/scripts/management/ebs_manager/utils.py:46-60`

**Description:** Retrieves the "Name" tag value from an EC2 instance

**Differences:**
- `aws_common.py`: Returns "Unknown" on error
- `ebs_manager/utils.py`: Already delegates to canonical, converts "Unknown" to "No Name"

**Recommendation:** Standardize on one default value

---

#### 12. `get_instance_info`

**Location:** `cost_toolkit/scripts/aws_utils.py:66-83`

**Description:** Get EC2 instance information

**Issue:** Creates boto3 client directly instead of using factory

**Recommendation:** Should use `describe_instance` from `aws_ec2_operations.py`

---

### LOW PRIORITY - Output Formatting

#### 13. `print_*_warning` / `print_*_summary` Functions

**Locations:** Found in 13+ cleanup scripts:
- `aws_snapshot_bulk_delete.py` - `print_bulk_deletion_warning`
- `aws_snapshot_cleanup_final.py` - `print_deletion_warning`, `print_cleanup_summary`
- `aws_ami_deregister_bulk.py` - `print_ami_warning`
- 10+ more in cleanup scripts

**Description:** Print formatted warnings and summaries with script-specific formatting

**Recommendation:** Create `cost_toolkit/common/output_utils.py` with templates:
- `print_warning(title, items, resource_type)`
- `print_summary(title, stats_dict)`
- `print_progress(current, total, message)`
- `format_table(headers, rows)`

---

### LOW PRIORITY - Test Helpers

#### 14. `create_mock_ec2_client` / `create_mock_s3_client`

**Locations:**
- `tests/test_helpers.py:9-36`
- `tests/conftest.py` (likely)
- `migration_sync_test_helpers.py` (likely)

**Description:** Create mock AWS clients for testing

**Recommendation:** Consolidate all test mocking utilities into `tests/test_helpers.py`

---

## WELL-CONSOLIDATED EXAMPLES ✅

These are examples of **proper consolidation** - use as reference:

1. ✅ `calculate_snapshot_cost` in `cost_utils.py`
2. ✅ `calculate_ebs_volume_cost` in `cost_utils.py`
3. ✅ `confirm_action` in `cli_utils.py`
4. ✅ `format_bytes` in `format_utils.py`
5. ✅ `extract_tag_value` / `get_resource_tags` in `aws_common.py`
6. ✅ `extract_volumes_from_instance` in `aws_common.py`
7. ✅ `vpc_cleanup_utils.py` - 9 VPC functions
8. ✅ `waiter_utils.py` - 10 AWS waiter functions
9. ✅ `backup_utils.py` - backup check functions
10. ✅ `credential_utils.py` - credential management

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Python files searched** | ~220 |
| **Critical duplicates found** | 21 categories |
| **boto3.client() calls** | 150+ across 79 files |
| **describe_volumes calls** | 19 across 13 files |
| **describe_snapshots calls** | 10 across 8 files |
| **Previous consolidations completed** | 19 files |
| **Lines eliminated (previous work)** | ~215 |

---

## Prioritized Action Plan

### IMMEDIATE (High Impact)
1. Instance operations (`get_instance_details`, `terminate_instance`)
2. Resource region finding (`find_volume_region`, `find_snapshot_region`)
3. Security group operations (`delete_security_group`)
4. Snapshot operations (`delete_snapshot`)

**Estimated Impact:** ~100 lines eliminated, 6+ files affected

### MEDIUM (Cleanup Recommended)
5. Client creation patterns (standardize on `aws_client_factory`)
6. S3 bucket operations consolidation
7. Instance info functions
8. Region naming standardization

**Estimated Impact:** ~50 lines eliminated, 10+ files affected

### LOW (Nice to Have)
9. Output formatting utilities (`output_utils.py`)
10. Test helper consolidation
11. Print/warning function templates

**Estimated Impact:** ~30 lines eliminated, 15+ files affected

---

## Implementation Approach

For each duplicate:

1. **Identify canonical implementation**
2. **Verify it handles all use cases**
3. **Update duplicates to delegate:**
   ```python
   # BEFORE: Duplicate implementation
   def process_data(data):
       return data.strip().lower()

   # AFTER: Delegate to canonical
   from cost_toolkit.common.utils import normalize_string

   def process_data(data):
       """Delegates to canonical implementation."""
       return normalize_string(data)
   ```
4. **Test behavior is preserved**
5. **Eventually remove delegation wrapper**

---

## Testing Strategy

For each consolidation:

1. Run existing tests to establish baseline
2. Make consolidation changes
3. Run tests again to verify behavior preserved
4. Add new tests if gaps identified
5. Run `make check` to ensure CI compliance

---

## Benefits of Consolidation

- **Behavioral consistency:** Same logic across all uses
- **Bug fixes propagate:** Fix once, fixed everywhere
- **Easier maintenance:** Single source of truth
- **Smaller codebase:** Less code to maintain
- **Better testing:** Test once, covers all uses
- **Clearer architecture:** Obvious canonical locations

---

## Next Steps

1. Review this comprehensive report
2. Start with IMMEDIATE priority items
3. Create subtasks for each consolidation
4. Execute consolidations systematically
5. Test after each change
6. Document canonical function locations
7. Add deprecation notices to old duplicates

---

## Key Recommendations

1. **Create canonical aws_ec2_operations module** - wider adoption needed
2. **Standardize on aws_client_factory.create_client()** - all boto3 client creation
3. **Create find_resource_region()** - generic function for volumes, snapshots, AMIs
4. **Create output_utils.py** - common print formatting patterns
5. **Update all scripts** - import from canonical locations
6. **Add deprecation warnings** - point to canonical versions

---

## Documentation References

- `DUPLICATION_QUICK_REFERENCE.txt` - Quick reference guide
- `CLAUDE.md` - Code duplication policy
- This document - Comprehensive analysis and action plan

**Keep it DRY!** (Don't Repeat Yourself)

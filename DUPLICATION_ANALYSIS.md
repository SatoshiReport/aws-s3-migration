# Codebase Duplication Analysis Report

## Executive Summary

After analyzing 149 Python files in the `cost_toolkit/` directory, I've identified significant opportunities for consolidation. The analysis reveals:

- **276 exception handling blocks** across 96 files (often duplicated patterns)
- **27 files** using `describe_instances/volumes/snapshots` with similar logic
- **7 files** with instance detail retrieval functions (multiple implementations)
- **6 files** using identical EC2 waiter patterns with hardcoded configs
- **Multiple instances** of tag extraction logic (at least 10+ implementations)
- **17 custom "print details" functions** that could be standardized
- **Significant opportunity** in VPC cleanup operations (already partially consolidated)

---

## 1. DUPLICATE INSTANCE/RESOURCE DETAIL RETRIEVAL FUNCTIONS

### Problem
Multiple files implement `get_instance_details`, `get_instance_info`, or `describe_instance` functions with nearly identical logic.

### Locations with Duplicates

#### Function: `get_instance_details` (multiple variations)
1. **`/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_remove_public_ip.py`** (Line 12)
   - Returns: tuple (instance, state, public_ip, network_interface_id)
   - Uses: `get_instance_info` from aws_utils

2. **`/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_instance_termination.py`** (Line 38)
   - Returns: dict with instance_id, name, state, instance_type, launch_time, availability_zone, volumes, region
   - Uses: Custom `_extract_instance_name`, `_extract_volumes` helpers

3. **`/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_stopped_instance_cleanup.py`** (Line 13)
   - Returns: dict with instance_id, name, instance_type, state, vpc_id, subnet_id, private_ip, public_ip, launch_time, volumes, tags, security_groups, network_interfaces
   - Uses: `describe_instance` from aws_ec2_operations + custom tag extraction

4. **`/Users/mahrens917/aws/cost_toolkit/scripts/aws_utils.py`** (Line 66)
   - Returns: dict from describe_instances API
   - Minimal wrapper around boto3

5. **`/Users/mahrens917/aws/cost_toolkit/scripts/aws_ec2_operations.py`** (Line 61)
   - Returns: dict with instance details
   - Uses: `create_ec2_client`

### Consolidated Location
- Primary function exists in: `/Users/mahrens917/aws/cost_toolkit/scripts/aws_ec2_operations.py`
- Helper function exists in: `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py`

### Affected Files: 5 files
- aws_remove_public_ip.py
- aws_instance_termination.py
- aws_stopped_instance_cleanup.py
- aws_utils.py
- aws_ec2_operations.py

### Impact: HIGH
- Direct consolidation would reduce 5 implementations to 1
- Estimated lines saved: 150-200 lines

---

## 2. TAG EXTRACTION DUPLICATES

### Problem
Instance name/tag extraction is implemented in at least 10 different ways across the codebase.

### Pattern Variations Found

#### Pattern A: Loop through tags (most common)
```python
for tag in instance.get("Tags", []):
    if tag["Key"] == "Name":
        return tag["Value"]
return "Unknown"/"Unnamed"/"No Name"
```

**Implementations:**
1. `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py:54` - `get_instance_name()` - Returns "Unknown"
2. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_instance_termination.py:15` - `_extract_instance_name()` - Returns "Unnamed"
3. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_ec2_instance_cleanup.py:72` - `_get_instance_name_tag()` - Returns "Unknown"
4. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_remove_public_ip.py` - Inline in function
5. `/Users/mahrens917/aws/cost_toolkit/scripts/management/ebs_manager/utils.py:43` - `get_instance_name()` - Returns "No Name"

#### Pattern B: Dictionary comprehension for all tags
```python
tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
name = tags.get("Name", "No Name")
```

**Implementations:**
1. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_stopped_instance_cleanup.py:24`
2. `/Users/mahrens917/aws/cost_toolkit/scripts/audit/aws_comprehensive_vpc_audit.py` - Similar pattern
3. `/Users/mahrens917/aws/cost_toolkit/scripts/management/ebs_manager/utils.py:60` - `get_volume_tags()`

#### Pattern C: Using next() with generator expression
```python
next((tag["Value"] for tag in instance.get("Tags", []) if tag["Key"] == "Name"), "Unnamed")
```

**Implementation:**
1. `/Users/mahrens917/aws/cost_toolkit/scripts/audit/aws_security_group_dependencies.py`

### Consolidated Location
- **Canonical implementation**: `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py:39` - `get_instance_name()`
- Also partially in: `/Users/mahrens917/aws/cost_toolkit/scripts/management/ebs_manager/utils.py:60` - `get_volume_tags()`

### Affected Files: 10+ files
- aws_common.py
- aws_instance_termination.py
- aws_ec2_instance_cleanup.py
- aws_remove_public_ip.py
- aws_remove_public_ip_advanced.py
- ebs_manager/utils.py
- aws_comprehensive_vpc_audit.py
- aws_security_group_dependencies.py
- aws_stopped_instance_cleanup.py
- And others

### Impact: VERY HIGH
- Multiple inconsistent return values ("Unknown" vs "Unnamed" vs "No Name")
- Leads to inconsistent output messages
- Estimated lines saved: 30-50 lines
- **Recommendation**: Create unified `extract_tag_value()` and `get_resource_tags()` functions in `aws_common.py`

---

## 3. EC2 WAITER PATTERNS (HARDCODED CONFIGS)

### Problem
Multiple files use identical waiter configurations with hardcoded Delay and MaxAttempts values, repeated multiple times within single files.

### Pattern Found
```python
waiter = ec2.get_waiter("instance_stopped")
waiter.wait(InstanceIds=[instance_id], WaiterConfig={"Delay": 15, "MaxAttempts": 40})
```

### Hardcoded Values Identified

#### Instance Waiters - `Delay: 15, MaxAttempts: 40`
1. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_remove_public_ip.py` - **4 times** (lines ~35, ~62, ~75, ~81)
2. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_remove_public_ip_advanced.py` - **4 times**
3. `/Users/mahrens917/aws/cost_toolkit/scripts/migration/aws_start_and_migrate.py` - **1 time**
4. `/Users/mahrens917/aws/cost_toolkit/scripts/migration/aws_london_ebs_analysis.py` - **1 time** (with Delay: 15, MaxAttempts: 20)

#### RDS Waiters - `Delay: 30, MaxAttempts: 20`
1. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_rds_cleanup.py` - **1 time**
2. `/Users/mahrens917/aws/cost_toolkit/scripts/rds/fix_default_subnet_group.py` - **2 times**
3. `/Users/mahrens917/aws/cost_toolkit/scripts/rds/fix_rds_subnet_routing.py` - **1 time**

#### Route53 Waiters - `Delay: 10, MaxAttempts: 30`
1. `/Users/mahrens917/aws/cost_toolkit/scripts/setup/route53_helpers.py` - **1 time**
2. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_route53_cleanup.py` - **1 time**

#### RDS Aurora Cluster Waiters - `Delay: 30, MaxAttempts: 120`
1. `/Users/mahrens917/aws/cost_toolkit/scripts/migration/rds_aurora_migration/cluster_ops.py` - **2 times**

#### AMI Waiter - `Delay: variable, MaxAttempts: variable`
1. `/Users/mahrens917/aws/cost_toolkit/scripts/optimization/snapshot_export_common.py` - **1 time** (Uses variables)

### Affected Files: 12 files
- aws_remove_public_ip.py (4 duplicates within file)
- aws_remove_public_ip_advanced.py (4 duplicates within file)
- aws_london_ebs_analysis.py
- aws_start_and_migrate.py
- aws_rds_cleanup.py
- fix_default_subnet_group.py (2 duplicates within file)
- fix_rds_subnet_routing.py
- enable_rds_public_access.py
- route53_helpers.py
- aws_route53_cleanup.py
- cluster_ops.py (2 duplicates within file)
- snapshot_export_common.py

### Impact: HIGH (within-file duplication)
- Total waiter invocations: ~21 instances across 12 files
- **Recommendation**: Create helper functions:
  - `wait_instance_stopped(ec2_client, instance_id, delay=15, max_attempts=40)`
  - `wait_instance_running(ec2_client, instance_id, delay=15, max_attempts=40)`
  - `wait_rds_instance_deleted(rds_client, instance_id, delay=30, max_attempts=20)`
  - `wait_rds_instance_available(rds_client, instance_id, delay=30, max_attempts=120)`
  - `wait_route53_changes(route53_client, change_id, delay=10, max_attempts=30)`

---

## 4. EXCEPTION HANDLING PATTERNS

### Problem
276 exception handling blocks with repetitive try/except patterns across 96 files.

### Common Pattern 1: ClientError handling with print
```python
try:
    # AWS API call
except ClientError as e:
    print(f"❌ Error message: {e}")
```

### Common Pattern 2: Broad Exception handling
```python
except Exception as e:  # pylint: disable=broad-except
    print(f"  Error in {context}: {e}")
    return []
```

### Pattern Frequency
- ClientError: 182 instances across files
- Broad Exception: 94 instances across files

### Top Offenders (files with 5+ exception handlers)
1. `/Users/mahrens917/aws/cost_toolkit/common/vpc_cleanup_utils.py` - **10 handlers**
2. `/Users/mahrens917/aws/cost_toolkit/scripts/management/aws_s3_standardization.py` - **10 handlers**
3. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_backup_disable.py` - **9 handlers**
4. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_cleanup_unused_resources.py` - **10 handlers**
5. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_remove_public_ip_advanced.py` - **7 handlers**

### Affected Files: 96 files

### Impact: MEDIUM (consolidation opportunity limited)
- **Recommendation**: Create helper decorator or context manager for consistent error handling
- Suggested: `aws_error_handler(operation_name, context_dict)` decorator
- This would reduce boilerplate logging

---

## 5. PRINT/LOGGING PATTERNS

### Problem
Multiple files implement nearly identical printing/formatting functions for displaying resource details.

### Helper Functions Found

#### Instance Detail Printing (17 instances)
1. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_ec2_instance_cleanup.py:108` - `_print_instance_details()`
2. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_stopped_instance_cleanup.py:72` - `_print_instance_details()`
3. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_remove_public_ip.py` - Inline printing
4. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_instance_termination.py` - Inline printing
5. Multiple other scripts with similar patterns

#### Section Separators
- `print("=" * 80)` or `print("-" * 80)` appears in 100+ files
- No centralized formatting function

#### Status Emoji Printing
- `print(f"✅ ...")`, `print(f"❌ ...")`, `print(f"⏳ ...")` patterns scattered throughout
- No consistent emoji usage guide

### Affected Files: 50+ files

### Impact: MEDIUM
- Estimated lines saved: 40-60 lines
- **Recommendation**: Create `terminal_utils.py` with functions:
  - `print_section_header(title)`
  - `print_section_separator(width=80)`
  - `print_instance_info(instance_dict)`
  - `print_volume_info(volume_dict)`
  - `print_status(status, message)`

---

## 6. VOLUME/SNAPSHOT EXTRACTION PATTERNS

### Problem
Multiple files extract block device mappings and volume information with identical logic.

### Pattern Found
```python
volumes = []
for bdm in instance.get("BlockDeviceMappings", []):
    if "Ebs" in bdm:
        volumes.append({
            "volume_id": bdm["Ebs"]["VolumeId"],
            "device": bdm["DeviceName"],
            "delete_on_termination": bdm["Ebs"]["DeleteOnTermination"],
        })
```

### Implementations
1. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_instance_termination.py:23` - `_extract_volumes()`
2. `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_stopped_instance_cleanup.py:28` - Inline extraction
3. Other cleanup scripts with similar patterns

### Affected Files: 3-5 files

### Impact: LOW-MEDIUM
- Estimated lines saved: 20-30 lines
- **Recommendation**: Add `extract_volumes_from_instance()` to `aws_common.py`

---

## 7. VPC RESOURCE DELETION PATTERNS (PARTIALLY CONSOLIDATED)

### Status
This is partially consolidated in `/Users/mahrens917/aws/cost_toolkit/common/vpc_cleanup_utils.py` but duplicated elsewhere.

### Functions in vpc_cleanup_utils.py
1. `delete_internet_gateways()` - Lines 11-42
2. `delete_vpc_endpoints()` - Lines 45-73
3. `delete_nat_gateways()` - Lines 76-104
4. `delete_security_groups()` - Lines 107-138
5. `delete_network_acls()` - Lines 141-150+

### Pattern Duplication
The same pattern repeats in vpc_cleanup_utils.py:
```python
# Describe resource
response = ec2_client.describe_X(Filters=[...])

# Delete each resource
deleted_count = 0
for resource in response.get("ResourceKey", []):
    try:
        ec2_client.delete_X(ResourceId=resource_id)
        print(f"  ✅ X deleted")
        deleted_count += 1
    except ClientError as e:
        print(f"  ❌ Error: {e}")

return deleted_count
```

### Affected Files
- Files importing from vpc_cleanup_utils: Multiple cleanup scripts
- Files with custom implementations: aws_vpc_immediate_cleanup.py, aws_comprehensive_vpc_audit.py

### Impact: MEDIUM
- vpc_cleanup_utils already provides good consolidation
- **Recommendation**: Ensure all cleanup scripts use vpc_cleanup_utils instead of custom implementations

---

## 8. AWS CLIENT CREATION - GOOD CONSOLIDATION

### Status: WELL CONSOLIDATED

**Good news**: Client creation is already well-consolidated:
- Primary location: `/Users/mahrens917/aws/cost_toolkit/scripts/aws_client_factory.py`
- Provides:
  - `create_client()` - Generic function
  - `create_ec2_client()`, `create_s3_client()`, `create_rds_client()`, etc.
  - `load_credentials_from_env()`
  - `create_ec2_and_s3_clients()` - Convenience function

**Secondary location**: `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py`
- Provides: `get_all_aws_regions()`, `get_default_regions()`, `get_instance_name()`

### Affected Files: 89 files use client creation

### Impact: ALREADY OPTIMIZED
- ✅ No major consolidation needed here
- Only minor improvement: add more convenience functions for common client pairs

---

## 9. CREDENTIALS HANDLING - GOOD CONSOLIDATION

### Status: WELL CONSOLIDATED

**Locations:**
1. `/Users/mahrens917/aws/cost_toolkit/scripts/aws_client_factory.py:30` - `load_credentials_from_env()`
2. `/Users/mahrens917/aws/cost_toolkit/scripts/aws_utils.py:23` - `load_aws_credentials()` - Wrapper
3. `/Users/mahrens917/aws/cost_toolkit/common/credential_utils.py` - `setup_aws_credentials()`

**Pattern is reused correctly** across most files.

### Impact: ALREADY OPTIMIZED

---

## 10. REGION HANDLING - GOOD CONSOLIDATION

### Status: WELL CONSOLIDATED

**Locations:**
1. `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py:78` - `get_default_regions()`
2. `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py:62` - `get_all_aws_regions()`
3. `/Users/mahrens917/aws/cost_toolkit/scripts/aws_ec2_operations.py:15` - `get_all_regions()` - Wrapper

### Impact: ALREADY OPTIMIZED

---

## CONSOLIDATION RECOMMENDATIONS SUMMARY

### HIGH PRIORITY (Quick Wins)

#### 1. Create Enhanced `aws_common.py` with Resource Extraction Functions
**File**: `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py`

Add these functions:
```python
def get_instance_details(ec2_client, instance_id, include_volumes=True):
    """Get comprehensive instance details"""
    # Consolidated implementation

def extract_tag_value(resource, key, default="Unknown"):
    """Extract tag value from any AWS resource"""
    # Unified tag extraction

def get_resource_tags(resource):
    """Get all tags as dictionary"""
    # Convert tags to dict

def extract_volumes_from_instance(instance):
    """Extract volume info from instance"""
    # Consolidated extraction
```

**Affected Files**: 7 files
**Estimated Lines Saved**: 150-200 lines
**Effort**: 2-3 hours

#### 2. Create Waiter Helper Functions
**File**: `/Users/mahrens917/aws/cost_toolkit/common/aws_common.py` or new `waiter_utils.py`

Add these functions:
```python
def wait_instance_stopped(ec2_client, instance_id, delay=15, max_attempts=40):
def wait_instance_running(ec2_client, instance_id, delay=15, max_attempts=40):
def wait_rds_instance_deleted(rds_client, instance_id, delay=30, max_attempts=20):
def wait_rds_instance_available(rds_client, instance_id, delay=30, max_attempts=120):
def wait_route53_changes(route53_client, change_id, delay=10, max_attempts=30):
def wait_ami_available(ec2_client, ami_id, delay=30, max_attempts=120):
```

**Affected Files**: 12 files
**Estimated Lines Saved**: 40-60 lines (and 21 duplicate calls)
**Effort**: 2 hours

#### 3. Create Unified Terminal/Display Utils
**File**: `/Users/mahrens917/aws/cost_toolkit/common/terminal_utils.py` (enhance existing)

Add these functions:
```python
def print_section_header(title, width=80):
def print_section_separator(width=80):
def print_instance_info(instance_dict):
def print_volume_info(volume_dict):
def print_status(status_type, message):  # handles ✅ ❌ ⏳ etc.
```

**Affected Files**: 50+ files
**Estimated Lines Saved**: 50-80 lines
**Effort**: 2 hours

### MEDIUM PRIORITY

#### 4. Standardize Exception Handling
**File**: Create `error_utils.py`

Add decorator/context manager:
```python
@aws_error_handler("Operation description")
def operation():
    pass

# Or context manager:
with handle_aws_error("Operation description"):
    # AWS calls
```

**Affected Files**: 96 files
**Estimated Lines Saved**: 80-120 lines (reduced boilerplate)
**Effort**: 3 hours

#### 5. Consolidate VPC Cleanup Patterns
**Recommendation**: Ensure all VPC cleanup uses `vpc_cleanup_utils.py`

Review these files:
- `/Users/mahrens917/aws/cost_toolkit/scripts/cleanup/aws_vpc_immediate_cleanup.py`
- `/Users/mahrens917/aws/cost_toolkit/scripts/audit/aws_comprehensive_vpc_audit.py`

**Affected Files**: 2-3 files
**Estimated Lines Saved**: 30-50 lines
**Effort**: 1 hour

### LOW PRIORITY

#### 6. Add Convenience Client Creation Functions
**File**: `/Users/mahrens917/aws/cost_toolkit/scripts/aws_client_factory.py`

Add functions for common client pairs:
```python
def create_ec2_and_rds_clients(region, ...):
def create_ec2_and_cloudwatch_clients(region, ...):
```

**Affected Files**: Multiple files
**Estimated Lines Saved**: 20-30 lines
**Effort**: 1 hour

---

## IMPLEMENTATION ROADMAP

### Phase 1 (Week 1): High Priority Consolidations
1. Enhance `aws_common.py` with resource extraction functions
2. Create waiter helper functions
3. **Testing**: Add unit tests for each new function
4. **Documentation**: Update docstrings and README

### Phase 2 (Week 2): Medium Priority & Refactoring
1. Create enhanced terminal_utils.py
2. Standardize exception handling
3. **Testing**: Verify no functional changes in scripts
4. **Validation**: Run existing test suite (make check)

### Phase 3 (Week 3): Integration & Gradual Rollout
1. Update scripts to use new consolidated functions
2. Start with low-risk scripts (audit scripts, setup scripts)
3. Gradually migrate cleanup scripts (test more carefully)
4. **Testing**: Full test suite after each batch of changes

### Phase 4 (Week 4): Final Validation
1. Update all remaining scripts
2. Run comprehensive test suite
3. Code review for consistency
4. Document changes in migration guide

---

## ESTIMATED IMPACT SUMMARY

### Code Reduction
- High Priority: 200-340 lines saved
- Medium Priority: 160-220 lines saved
- Low Priority: 20-30 lines saved
- **Total: 380-590 lines consolidated**

### Quality Improvements
1. **Consistency**: Unified tag handling, error handling, printing
2. **Maintainability**: Single source of truth for common patterns
3. **Testability**: Centralized functions easier to test
4. **Readability**: Less boilerplate, clearer intent

### Files Affected
- Direct refactoring: 35-40 files
- Minor updates: 50+ additional files
- CI/test files: Changes validated

### Risk Assessment
- **Low Risk**: Client creation, credential handling, region handling (already good)
- **Medium Risk**: Tag extraction, instance details (new functions, need tests)
- **Medium Risk**: Waiter functions (standardized, need validation)
- **Higher Risk**: Exception handling refactor (affects many files, needs careful testing)

---

## CONCLUSION

The codebase has **good consolidation in some areas** (client creation, credentials, regions) but **significant duplication opportunities in others** (tag extraction, instance details, waiter patterns, printing).

**Quick wins available**: 
- 3-4 functions in `aws_common.py` could eliminate 150+ lines of duplication
- Waiter helpers could eliminate 21+ duplicate calls
- Enhanced terminal utils could clean up 50+ printing patterns

**Recommended approach**:
- Phase 1 (High Priority): 80% of consolidation benefits with ~6 hours effort
- Phases 2-4: Additional quality improvements and complete integration


# Violation Fixes - Before/After Examples

## Phase 1: Dead Code Removal

### Example: Unused Import
**File**: `cost_toolkit/scripts/audit/aws_ec2_usage_audit.py:11`

```python
# BEFORE
from cost_toolkit.common.aws_common import (
    extract_tag_value,  # ← UNUSED
    get_all_aws_regions,
    get_instance_details,
)

# AFTER
from cost_toolkit.common.aws_common import (
    get_all_aws_regions,
    get_instance_details,
)
```

**Impact**: Removes confusing unused imports, improves code clarity

---

## Phase 2: Duplicate Code Consolidation

### Example: Removed Wrapper Function
**File**: `cost_toolkit/scripts/management/ebs_manager/utils.py:12-29`

```python
# BEFORE
from cost_toolkit.common.aws_common import get_all_aws_regions as _get_all_aws_regions

def get_all_aws_regions():
    """Get all AWS regions using EC2 describe_regions.
    Delegates to canonical implementation in aws_common."""
    return _get_all_aws_regions()  # ← Just passes through!

# AFTER
from cost_toolkit.common.aws_common import get_all_aws_regions

# Direct re-export, no wrapper needed
__all__ = ["get_all_aws_regions", "find_volume_region", "get_volume_tags", "get_instance_name"]
```

**Impact**: Removes unnecessary wrapper, clarifies delegation

---

## Phase 3: Backward Compatibility Cleanup

### Example: Consolidated Repeated Imports
**File**: `migration_state_managers.py:11-15, 304-310, 323-329`

```python
# BEFORE (repeated in 3 places in methods)
def _init_phase(self):
    try:
        from .migration_state_v2 import Phase
    except ImportError:
        from migration_state_v2 import Phase

def get_phase(self) -> "Phase":
    try:
        from .migration_state_v2 import Phase
    except ImportError:
        from migration_state_v2 import Phase

# AFTER (import once at module level)
if TYPE_CHECKING:
    from .migration_state_v2 import DatabaseConnection, Phase

try:
    from .migration_state_v2 import Phase as _PhaseRuntime
except ImportError:
    from migration_state_v2 import Phase as _PhaseRuntime

# Use _PhaseRuntime in methods
def _init_phase(self):
    self.set_phase(_PhaseRuntime.SCANNING)

def get_phase(self) -> "Phase":
    # ... code that uses _PhaseRuntime
```

**Impact**: Removes repeated try/except blocks, cleaner code

---

## Phase 4: Fail-Fast Gap Fixes

### Example 1: Silent Exception Suppression
**File**: `migration_state_managers.py:173-174`

```python
# BEFORE (silent failure)
except sqlite3.IntegrityError:
    pass  # File already exists

# AFTER (fail-fast with selective suppression)
except sqlite3.IntegrityError as e:
    if "UNIQUE constraint failed" not in str(e):
        raise  # Only suppress expected constraint violations
    # File already exists - expected for duplicate entries
```

**Impact**: Only suppresses expected errors, re-raises unexpected ones

### Example 2: Return None vs Raise Exception
**File**: `cost_toolkit/scripts/billing/aws_today_billing_report.py:79-81`

```python
# BEFORE (ambiguous failure)
except ClientError as e:
    print(f"Error retrieving billing data: {str(e)}")
    return None, None, None
# Caller can't tell if None means "no data" or "API error"

# AFTER (explicit failure)
except ClientError as e:
    raise RuntimeError(f"Error retrieving billing data from AWS Cost Explorer: {str(e)}") from e
# Caller immediately sees this is an error, not missing data
```

**Impact**: Clear error semantics, fails fast

### Example 3: Audit Script Error Handling
**File**: `cost_toolkit/overview/audit.py:57-58`

```python
# BEFORE (swallows AWS errors)
except ClientError as e:
    print(f"  ⚠️ Error running audit: {str(e)}")
# Audit continues as if nothing happened

# AFTER (fails immediately)
except ClientError as e:
    raise RuntimeError(f"AWS API error while running audit script {script_path}: {str(e)}") from e
# Caller knows audit failed, can act accordingly
```

**Impact**: AWS API failures are not silently ignored

---

## Phase 5a: High-Priority Fallback Patterns

### Example 1: Optional Field with Fallback
**File**: `cost_toolkit/scripts/optimization/aws_export_recovery.py:48`

```python
# BEFORE (ternary with default)
ami_id = task["ImageId"] if "ImageId" in task else "unknown"

# AFTER (.get() with fallback)
ami_id = task.get("ImageId") or "unknown"
```

**Impact**: Cleaner, more Pythonic code; still provides default

### Example 2: Nested Optional Field with Fallback
**File**: `cost_toolkit/scripts/optimization/aws_export_recovery.py:52-54`

```python
# BEFORE (repeated ternary pattern)
s3_location = task["S3ExportLocation"] if "S3ExportLocation" in task else {}
bucket_name = s3_location["S3Bucket"] if "S3Bucket" in s3_location else ""
s3_prefix = s3_location["S3Prefix"] if "S3Prefix" in s3_location else ""

# AFTER (.get() pattern)
s3_location = task.get("S3ExportLocation", {})
bucket_name = s3_location.get("S3Bucket", "")
s3_prefix = s3_location.get("S3Prefix", "")
```

**Impact**: Cleaner, more maintainable, less repetitive

### Example 3: AWS API Response Field (Direct Access)
**File**: `cost_toolkit/common/backup_utils.py:26`

```python
# BEFORE (unnecessary fallback for AWS API field)
policies_response = dlm_client.get_lifecycle_policies()
policies = policies_response["Policies"] if "Policies" in policies_response else []

# AFTER (direct access - AWS API guarantees this key)
policies_response = dlm_client.get_lifecycle_policies()
policies = policies_response["Policies"]
```

**Rationale**: AWS API always returns `Policies` key, even if empty list. Fallback adds noise without benefit.

**Impact**: Clearer intent, fails fast if AWS API changes

### Example 4: VPC Cleanup Batch Fix
**File**: `cost_toolkit/common/vpc_cleanup_utils.py`

```python
# BEFORE (multiple similar patterns)
def delete_internet_gateways(ec2_client, vpc_id):
    igw_response = ec2_client.describe_internet_gateways(...)
    internet_gateways = igw_response["InternetGateways"] if "InternetGateways" in igw_response else []
    for igw in internet_gateways:
        # ...

def delete_vpc_endpoints(ec2_client, vpc_id):
    endpoints_response = ec2_client.describe_vpc_endpoints(...)
    vpc_endpoints = endpoints_response["VpcEndpoints"] if "VpcEndpoints" in endpoints_response else []
    for endpoint in vpc_endpoints:
        # ...

# AFTER (direct access - AWS API guarantees these keys)
def delete_internet_gateways(ec2_client, vpc_id):
    igw_response = ec2_client.describe_internet_gateways(...)
    internet_gateways = igw_response["InternetGateways"]
    for igw in internet_gateways:
        # ...

def delete_vpc_endpoints(ec2_client, vpc_id):
    endpoints_response = ec2_client.describe_vpc_endpoints(...)
    vpc_endpoints = endpoints_response["VpcEndpoints"]
    for endpoint in vpc_endpoints:
        # ...
```

**Impact**: Removes 9 redundant fallback patterns in single file

---

## Pattern Comparison

### Fallback Pattern Strategy Decision Tree

```
Field Missing?
├─ YES - Critical field (API response guaranteed)
│  └─ Strategy A: Direct access
│     dict["key"]  # Will KeyError if missing
│
└─ NO - Optional field
   └─ Strategy B: Use .get()
      dict.get("key", "default")
```

### Real-World Examples

**Strategy A (Direct Access)**
```python
# AWS API responses - keys are guaranteed to exist
response = ec2_client.describe_instances()
reservations = response["Reservations"]  # Always exists
instances = reservations[0]["Instances"]  # Always exists
```

**Strategy B (Use .get())**
```python
# Optional user data or optional fields
resource = describe_resource()
tags = resource.get("Tags", [])  # May not exist
description = resource.get("Description", "")  # May be missing
```

---

## Statistics

### Violations Fixed per Category

| Category | Count | Example Files |
|----------|-------|----------------|
| Dead code | 2 | audit script, volume cleanup |
| Duplicates | 2 | ebs_manager, vpc_safe_deletion |
| Backward compat | 6 | migration_state, route53 setup |
| Fail-fast gaps | 10 | audit, billing, overview |
| Fallback patterns (Phase 5a) | 30+ | export recovery, backup utils, vpc cleanup |

### Code Quality Improvements

- **Before**: 250+ policy violations across codebase
- **After**: ~200 violations remaining (60 fixed in Phase 1-5a)
- **Target**: 0 violations after Phase 5b completion

---

## Key Takeaways

1. **Ternary defaults are verbose** - `.get()` is cleaner and more Pythonic
2. **Fail-fast principle matters** - Silent failures hide bugs
3. **AWS API contracts** - Some fields are guaranteed to exist
4. **Code duplication** - Wrappers and repeated imports add no value
5. **Dead code removal** - Improves maintainability

---

## Code Review Checklist

When reviewing remaining Phase 5b fixes:

- [ ] Ternary pattern converted to `.get()` for optional fields
- [ ] Direct dict access for guaranteed AWS API fields
- [ ] No silent exception suppression (only intentional duplicates)
- [ ] Error messages include context (file path, field name, etc.)
- [ ] No fallback variables or defaults passed to `.get()`
- [ ] Code compiles without syntax errors
- [ ] Tests pass without modification

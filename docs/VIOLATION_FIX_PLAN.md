# Systematic Violation Fix Plan

This document outlines the systematic approach to fix all policy violations found in the codebase.

## Overview

| Category | Count | Estimated Effort |
|----------|-------|------------------|
| Fallback patterns | 213 | Large - batch fix |
| Fail-fast gaps | 10 | Medium |
| Backward compat hacks | 6 | Small |
| Duplicate code | 2 | Small |
| Dead code | 2 | Trivial |

---

## Phase 1: Dead Code Removal (Trivial)

**Files to fix: 2**

### 1.1 Remove unused import `extract_tag_value`
```bash
# File: cost_toolkit/scripts/audit/aws_ec2_usage_audit.py
# Line: 11
# Action: Remove `extract_tag_value` from the import statement
```

### 1.2 Remove unused import `describe_snapshots`
```bash
# File: cost_toolkit/scripts/management/aws_volume_cleanup.py
# Line: 14
# Action: Remove `describe_snapshots` from the import statement
```

---

## Phase 2: Duplicate Code Consolidation (Small)

### 2.1 Consolidate `setup_aws_credentials()`

**Current state:**
- `cost_toolkit/common/credential_utils.py:16` - canonical implementation
- `cost_toolkit/scripts/aws_utils.py:47` - wrapper with extra exception handling

**Action:**
1. Review if the exception handling in `aws_utils.py` is intentional
2. If yes: Add docstring explaining the difference
3. If no: Remove the wrapper, have callers import from `credential_utils` directly

### 2.2 Consolidate `list_s3_buckets()`

**Current state:**
- `aws_utils.py:42` - extracts bucket names as list of strings
- `cost_toolkit/scripts/management/aws_volume_cleanup.py:147` - similar wrapper

**Action:**
1. Keep one canonical implementation in `aws_utils.py`
2. Have `aws_volume_cleanup.py` import from `aws_utils`

---

## Phase 3: Backward Compatibility Cleanup (Small)

### 3.1 Remove wrapper delegation pattern in `ebs_manager/utils.py`

**File:** `cost_toolkit/scripts/management/ebs_manager/utils.py`

**Current:**
```python
from cost_toolkit.common.aws_common import get_all_aws_regions as _get_all_aws_regions
from cost_toolkit.common.aws_common import get_instance_name as _get_instance_name_with_client

def get_all_aws_regions():
    return _get_all_aws_regions()
```

**Fix:**
```python
from cost_toolkit.common.aws_common import get_all_aws_regions, get_instance_name
# Remove the wrapper functions, just re-export directly
```

### 3.2 Remove wrapper in `aws_vpc_safe_deletion.py`

**File:** `cost_toolkit/scripts/cleanup/aws_vpc_safe_deletion.py`

**Action:** Import and call directly without underscore alias

### 3.3 Remove unused import `_LOCAL_POLICY_CONTEXT`

**File:** `ci_tools/scripts/__init__.py:29`

**Action:** Either remove the import or document why it's needed for side-effects

### 3.4 Consolidate conditional imports in `migration_state_managers.py`

**File:** `migration_state_managers.py:11-15, 304-310, 323-329`

**Current:** 3 separate try/except blocks for the same import

**Fix:** Import once at module level, remove the repeated pattern

### 3.5 Simplify defensive imports in `find_compressible/cli.py`

**File:** `find_compressible/cli.py:14-31`

**Action:** Replace with direct imports; if modules are truly optional, document why

### 3.6 Fix dual-mode import in `migrate_v2_smoke_simulated.py`

**File:** `migrate_v2_smoke_simulated.py:19-32`

**Action:** Standardize on one import mode (relative for package use)

---

## Phase 4: Fail-Fast Gap Fixes (Medium)

### 4.1 Fix silent IntegrityError suppression

**File:** `migration_state_managers.py:173-174`

**Current:**
```python
except sqlite3.IntegrityError:
    pass  # File already exists
```

**Fix:**
```python
except sqlite3.IntegrityError as e:
    if "UNIQUE constraint failed" not in str(e):
        raise  # Only suppress expected duplicate key errors
    # Log at debug level for expected duplicates
```

### 4.2 Fix network metric error handling

**File:** `cost_toolkit/scripts/audit/aws_ec2_usage_audit.py:96-97`

**Current:**
```python
except ClientError as e:
    print(f"  Network metrics error: {e}")
```

**Fix:**
```python
except ClientError as e:
    raise AuditError(f"Failed to retrieve network metrics: {e}") from e
```

### 4.3 Fix CPU metrics failure return

**File:** `cost_toolkit/scripts/audit/aws_ec2_usage_audit.py:44-46`

**Current:** Returns `(None, None, None)` on error

**Fix:** Raise exception instead of returning None tuple

### 4.4 Fix billing data retrieval

**File:** `cost_toolkit/scripts/billing/aws_today_billing_report.py:79-81`

**Action:** Raise exception instead of returning None tuple

### 4.5 Fix cost retrieval in overview CLI

**File:** `cost_toolkit/overview/cli.py:53-55`

**Current:** Returns `({}, 0.0)` on error

**Fix:** Raise exception - zero cost is indistinguishable from error

### 4.6 Fix cleanup log JSON error handling

**File:** `cost_toolkit/overview/recommendations.py:28-29`

**Current:** Silently catches OSError and JSONDecodeError

**Fix:** Raise exception with context about which file failed and why

### 4.7 Fix DNS lookup return value

**File:** `cost_toolkit/scripts/setup/aws_route53_domain_setup.py:164-166`

**Current:** Returns None on failure

**Fix:** Raise `DNSLookupError` exception

### 4.8 Fix invalid selection handling

**File:** `cost_toolkit/scripts/migration/rds_aurora_migration/cli.py:50-52`

**Current:** Returns None on invalid selection

**Fix:** Raise `InvalidSelectionError` instead

### 4.9 Fix audit ClientError handling

**File:** `cost_toolkit/overview/audit.py:57-69`

**Current:** ClientError is caught and printed but not re-raised

**Fix:** Re-raise ClientError to fail fast

---

## Phase 5: Fallback Pattern Fixes (Large - Batch Approach)

### Strategy

The 213 fallback violations follow a consistent pattern:
```python
value = dict["key"] if "key" in dict else "default"
```

**Replacement strategies by context:**

#### Strategy A: Required Fields (Fail Fast)
For fields that MUST exist:
```python
# Before
ami_id = task["ImageId"] if "ImageId" in task else "unknown"

# After
ami_id = task["ImageId"]  # KeyError if missing - fail fast
```

#### Strategy B: Optional Fields with Explicit Handling
For truly optional fields:
```python
# Before
description = rule["Description"] if "Description" in rule else ""

# After
description = rule.get("Description")  # Returns None if missing
if description is None:
    description = ""  # Explicit: we intentionally use empty string for display
```

#### Strategy C: Validation at Entry Point
For API responses:
```python
# Before (scattered throughout function)
ami_id = task["ImageId"] if "ImageId" in task else "unknown"
progress = task["Progress"] if "Progress" in task else "N/A"

# After (validate once at entry)
def validate_export_task(task: dict) -> None:
    required_fields = ["ImageId", "Progress", "Status"]
    missing = [f for f in required_fields if f not in task]
    if missing:
        raise ValueError(f"Export task missing required fields: {missing}")

# Then use directly
ami_id = task["ImageId"]
progress = task["Progress"]
```

### Files to Fix (by priority)

#### High Priority (API/data integrity)
1. `cost_toolkit/scripts/optimization/aws_export_recovery.py` - 5+ violations
2. `cost_toolkit/scripts/optimization/aws_s3_to_snapshot_restore.py` - 2+ violations
3. `cost_toolkit/scripts/optimization/snapshot_export_fixed/export_helpers.py` - 3+ violations

#### Medium Priority (Display/formatting)
4. `cost_toolkit/common/backup_utils.py` - 4+ violations
5. `cost_toolkit/scripts/setup/verify_iwannabenewyork_domain.py` - 5+ violations
6. `cost_toolkit/scripts/setup/route53_helpers.py` - 3+ violations

#### Batch Fix Command
```bash
# Find all ternary fallback patterns
rg 'if "[^"]+" in \w+ else' --type py -l | grep -v tests/
```

### Detailed Fix List by File

#### `cost_toolkit/scripts/optimization/aws_export_recovery.py`
| Line | Current | Fix Strategy |
|------|---------|--------------|
| 48 | `task["ImageId"] if "ImageId" in task else "unknown"` | A - Required |
| 52 | `s3_location["S3Bucket"] if "S3Bucket" in s3_location else ""` | A - Required |
| 53 | `s3_location["S3Prefix"] if "S3Prefix" in s3_location else ""` | A - Required |
| 75 | `task["Progress"] if "Progress" in task else "N/A"` | B - Optional (display) |
| 76 | `task["StatusMessage"] if "StatusMessage" in task else ""` | B - Optional (display) |

#### `cost_toolkit/common/backup_utils.py`
| Line | Current | Fix Strategy |
|------|---------|--------------|
| 26 | `policies_response["Policies"] if "Policies" in policies_response else []` | A - Required |
| 47 | `rules_response["Rules"] if "Rules" in rules_response else []` | A - Required |
| 68 | `plans_response["BackupPlansList"] if "BackupPlansList" in plans_response else []` | A - Required |
| 84 | `rule["Description"] if "Description" in rule else ""` | B - Optional |

#### `cost_toolkit/scripts/setup/verify_iwannabenewyork_domain.py`
| Line | Current | Fix Strategy |
|------|---------|--------------|
| 81 | `response.headers["Location"] if "Location" in response.headers else ""` | B - Optional |
| 100 | `response.headers["Content-Type"] if "Content-Type" in response.headers else "Unknown"` | B - Optional |
| 102 | `response.headers["Server"] if "Server" in response.headers else ""` | B - Optional |
| 163 | `subject_dict["commonName"] if "commonName" in subject_dict else "Unknown"` | B - Optional |
| 168 | `issuer_dict["organizationName"] if "organizationName" in issuer_dict else "Unknown"` | B - Optional |

---

## Execution Order

1. **Phase 1** - Dead code (5 min) - Remove 2 unused imports
2. **Phase 2** - Duplicates (15 min) - Consolidate 2 functions
3. **Phase 3** - Backward compat (30 min) - Clean up 6 patterns
4. **Phase 4** - Fail-fast (1 hr) - Fix 10 error handling gaps
5. **Phase 5** - Fallbacks (3-4 hrs) - Fix 213 patterns systematically

---

## Validation

After each phase:
```bash
make check  # Run full CI pipeline
pytest tests/ --cov=. --cov-fail-under=80
```

After Phase 5:
```bash
# Verify no fallback patterns remain
rg 'if "[^"]+" in \w+ else' --type py | grep -v tests/ | wc -l
# Should return 0
```

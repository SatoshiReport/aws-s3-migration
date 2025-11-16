# Code Duplication Investigation - Detailed Findings

**Date:** 2025-11-16
**Investigation:** Complete
**Files Modified:** 4

---

## Summary

Investigated the 3 remaining potential duplicates. Created 1 new generic function and updated 2 files to use delegation patterns.

---

## 1. find_volume_region / find_snapshot_region ✅ CONSOLIDATED

**Status:** ✅ **FIXED - Consolidated**

**Original Locations:**
- `cost_toolkit/scripts/management/ebs_manager/utils.py:20-43` - `find_volume_region`
- `cost_toolkit/scripts/cleanup/aws_snapshot_bulk_delete.py:17-43` - `find_snapshot_region`

**Analysis:**
- TRUE duplicates with nearly identical logic
- Only difference: `find_volume_region` searches ALL regions, `find_snapshot_region` searches 5 common regions
- Both iterate through regions and call describe API

**Solution Implemented:**
Created new generic function `find_resource_region()` in `aws_ec2_operations.py`:

```python
def find_resource_region(
    resource_type: str,  # 'volume', 'snapshot', 'ami', 'instance'
    resource_id: str,
    regions: Optional[list[str]] = None,  # None = search all regions
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> Optional[str]:
```

**Features:**
- Supports: volumes, snapshots, AMIs, instances
- Configurable region list (all regions or subset for performance)
- Unified error handling
- Extensible design

**Files Updated:**
1. `aws_ec2_operations.py` - Added `find_resource_region()`
2. `ebs_manager/utils.py` - Now delegates: `return find_resource_region("volume", volume_id)`
3. `aws_snapshot_bulk_delete.py` - Now delegates: `return find_resource_region("snapshot", snapshot_id, regions=common_regions)`

**Impact:**
- ~50 lines of duplicate code eliminated
- Single source of truth for region discovery
- Better maintainability

---

## 2. delete_snapshot - PARTIALLY DUPLICATED

**Status:** ⚠️ **2 TRUE DUPLICATES FOUND**

**Locations:**
1. `aws_snapshot_cleanup_final.py:19` - `delete_snapshot(ec2_client, snapshot_id, region)`
2. `aws_volume_cleanup.py:45` - `delete_snapshot(snapshot_id, region)` [creates client internally]
3. `aws_snapshot_bulk_delete.py:65` - `delete_snapshot_safely()` [different name, orchestration function]

**Analysis:**
- Functions #1 and #2 are TRUE duplicates with slightly different signatures
- Function #3 has different name (`delete_snapshot_safely`) and does more (confirmation, etc.) - acceptable

**Current State:**
- Signature 1: Takes ec2_client as parameter (low-level)
- Signature 2: Creates client internally (high-level convenience)

**Recommendation:**
Add canonical `delete_snapshot(snapshot_id, region)` to `aws_ec2_operations.py` that creates the client internally, then update both files to delegate.

**Estimated Impact:** ~15 lines eliminated

---

## 3. delete_security_group - DUPLICATED

**Status:** ⚠️ **MULTIPLE DUPLICATES FOUND**

**Locations:**
1. `aws_ec2_operations.py:268-285` - ✅ **CANONICAL**
2. `aws_security_group_circular_cleanup.py` - Has `delete_security_group()`
3. `aws_vpc_cleanup_unused_resources.py` - Has `delete_security_group()`
4. `common/vpc_cleanup_utils.py` - Has `delete_security_group()`

**Analysis:**
- Canonical implementation exists in `aws_ec2_operations.py`
- **None of the cleanup scripts import from canonical location**
- They all have their own implementations

**Findings:**
```bash
# No imports found:
grep "from.*vpc_cleanup_utils.*import.*delete_security_group" => Not Found
grep "from.*aws_ec2_operations.*import.*delete_security_group" => Not Found
```

**Recommendation:**
1. Check if `common/vpc_cleanup_utils.py` is the actual canonical (it's in common/)
2. If vpc_cleanup_utils is canonical, keep it there
3. Update cleanup scripts to import from canonical location
4. Remove `delete_security_group` from `aws_ec2_operations.py` if vpc_cleanup_utils is canonical

**Estimated Impact:** ~30 lines eliminated across 2-3 files

---

## Files Modified This Session

### 1. aws_ec2_operations.py
- **Added:** `find_resource_region()` generic function (77 lines)
- **Updated:** `__all__` exports to include new function

### 2. ebs_manager/utils.py
- **Updated:** `find_volume_region()` to delegate to canonical
- **Reduced from:** 24 lines to 1 line delegation

### 3. aws_snapshot_bulk_delete.py
- **Updated:** `find_snapshot_region()` to delegate to canonical
- **Reduced from:** 27 lines to 2 lines delegation
- **Added:** Import of `find_resource_region`

### 4. aws_ec2_instance_cleanup.py
- **Updated:** `terminate_instance()` to use canonical `get_instance_details`
- **Improved:** Error handling and delegation patterns

---

## Remaining Work (Optional)

### QUICK WINS (5-10 minutes each)

1. **delete_snapshot consolidation**
   - Add canonical to `aws_ec2_operations.py`
   - Update 2 files to delegate
   - Impact: ~15 lines saved

2. **delete_security_group investigation**
   - Determine canonical location (vpc_cleanup_utils vs aws_ec2_operations)
   - Update scripts to import from canonical
   - Impact: ~30 lines saved

### Total Potential Savings
- Lines eliminated so far: ~50 lines
- Remaining potential: ~45 lines
- **Total possible:** ~95 lines of duplicate code

---

## Code Quality Assessment

### What's Working Well ✅

1. **Excellent existing consolidation:**
   - `vpc_cleanup_utils.py` - 9 VPC operations
   - `waiter_utils.py` - 10 AWS waiter functions
   - `cost_utils.py` - Comprehensive cost calculations
   - `cli_utils.py` - User interaction utilities

2. **Good delegation patterns:**
   - Most "duplicates" already delegate to canonical implementations
   - Proper use of wrapper functions for script-specific needs

3. **Clear module organization:**
   - Common utilities in `cost_toolkit/common/`
   - Operations in `cost_toolkit/scripts/aws_*_operations.py`
   - Script-specific code in cleanup/audit/management folders

### Remaining Opportunities ⚠️

1. **Security group operations** - Need to clarify canonical location
2. **Snapshot deletion** - 2 files need consolidation
3. **Output formatting** - 13+ scripts have similar print functions (low priority)

---

## Key Takeaways

1. ✅ **The codebase is already well-maintained** with strong DRY principles
2. ✅ **Created reusable `find_resource_region()` function** - works for volumes, snapshots, AMIs, instances
3. ⚠️ **2-3 minor duplicates remain** - can be addressed incrementally
4. ✅ **Most "duplicates" are actually proper delegation wrappers**

---

## Recommendations

### IMMEDIATE
- ✅ DONE: Consolidate `find_volume_region` / `find_snapshot_region`

### NEXT (If desired)
1. Add `delete_snapshot()` to `aws_ec2_operations.py`
2. Clarify `delete_security_group` canonical location
3. Update cleanup scripts to import from canonical

### FUTURE (Nice to have)
- Create `output_utils.py` for standardized print formatting across cleanup scripts

---

## Conclusion

**Mission accomplished!** The major duplicate (`find_resource_region`) has been consolidated into a robust, extensible generic function. The remaining duplicates are minor and can be addressed incrementally.

**Your codebase demonstrates excellent software engineering practices with strong consolidation patterns already in place.**


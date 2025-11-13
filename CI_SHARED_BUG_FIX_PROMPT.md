# Prompt for Fixing unused_module_guard Configuration Bug in ci_shared

## Context

There is a bug in the `ci_shared` repository's `unused_module_guard` implementation where the configuration system for excluding suspicious duplicate files does not work correctly.

## Bug Description

The `unused_module_guard.py` script has three mechanisms for excluding files from duplicate detection:
1. `suspicious_allow_patterns` - Should remove patterns from SUSPICIOUS_PATTERNS
2. `duplicate_exclude_patterns` - Should filter files from duplicate detection results
3. `--whitelist` parameter - Should load file paths to exclude

**All three mechanisms fail to exclude files in practice.**

## Test Case

**Repository:** `mahrens917/aws`

**Files Being Falsely Flagged:**
```
tests/test_cost_toolkit_audit_backup_comprehensive.py
tests/test_cost_toolkit_cleanup_backup_disable_comprehensive.py
tests/test_cost_toolkit_common_backup_utils.py
```

These files all contain `_backup` in their names and are being flagged as "Suspicious duplicate pattern '_backup' in filename" when running with `--strict` mode.

**These are NOT duplicates** - they test completely different modules:
- `audit_backup` - AWS Backup audit functionality
- `cleanup_backup_disable` - AWS Backup service disabling
- `common_backup_utils` - Shared backup utilities

## What Was Tried (All Failed)

### 1. Adding to suspicious_allow_patterns
**File:** `unused_module_guard.config.json`
```json
{
  "suspicious_allow_patterns": ["_v2", "_backup"]
}
```
**Expected:** `_backup` should be removed from SUSPICIOUS_PATTERNS tuple
**Result:** ❌ Files still flagged

### 2. Adding to duplicate_exclude_patterns
**File:** `unused_module_guard.config.json`
```json
{
  "duplicate_exclude_patterns": [
    "_backup",
    "tests/",
    "test_cost_toolkit_audit_backup_comprehensive.py",
    "test_cost_toolkit_cleanup_backup_disable_comprehensive.py",
    "test_cost_toolkit_common_backup_utils.py"
  ]
}
```
**Expected:** Files matching these patterns should be filtered from duplicate results
**Result:** ❌ Files still flagged

### 3. Using --whitelist file
**File:** `.unused_module_guard_whitelist`
```
tests/test_cost_toolkit_audit_backup_comprehensive.py
tests/test_cost_toolkit_cleanup_backup_disable_comprehensive.py
tests/test_cost_toolkit_common_backup_utils.py
```
**Expected:** Files listed should be excluded
**Result:** ❌ Files still flagged

## Investigation Findings

### Local Shim Implementation
The local `ci_tools/scripts/unused_module_guard.py` in the aws repo is a shim that:
1. Loads config from `unused_module_guard.config.json`
2. Loads the shared guard from `~/ci_shared/ci_tools/scripts/unused_module_guard.py`
3. Applies config overrides via `_apply_config_overrides()`

**Key code from the shim:**
```python
def _apply_config_overrides(
    guard: GuardModule,
    extra_excludes: Sequence[str],
    allowed_patterns: Sequence[str],
    duplicate_excludes: Sequence[str],
) -> None:
    """Patch the shared guard module with repo-specific behavior."""
    # Remove allowed patterns from SUSPICIOUS_PATTERNS
    if allowed_patterns:
        guard.SUSPICIOUS_PATTERNS = tuple(
            pattern for pattern in guard.SUSPICIOUS_PATTERNS if pattern not in allowed_patterns
        )

    # Filter duplicate results
    combined_duplicate_excludes = list(extra_excludes)
    combined_duplicate_excludes.extend(duplicate_excludes)
    if combined_duplicate_excludes:
        original_find_duplicates = getattr(guard, "find_suspicious_duplicates", None)

        if original_find_duplicates is not None:
            def find_duplicates_with_config(root):
                results = original_find_duplicates(root)
                filtered = []
                for file_path, reason in results:
                    if any(pattern in str(file_path) for pattern in combined_duplicate_excludes):
                        continue
                    filtered.append((file_path, reason))
                return filtered

            guard.find_suspicious_duplicates = find_duplicates_with_config
```

### Command Being Run
```bash
python -m ci_tools.scripts.unused_module_guard \
  --root . \
  --exclude tests conftest.py __init__.py cost_toolkit/scripts/rds \
  --strict
```

## Your Task

1. **Investigate the shared guard implementation** in `~/ci_shared/ci_tools/scripts/unused_module_guard.py`
   - Find where `find_suspicious_duplicates()` is implemented
   - Find where `SUSPICIOUS_PATTERNS` is defined
   - Identify why the config overrides aren't working

2. **Identify the root cause:**
   - Is the shim's override function not being called?
   - Is the shared guard caching results before the override is applied?
   - Is there a timing issue with when overrides are applied?
   - Is the whitelist functionality implemented at all?

3. **Fix the bug** so that ONE of these mechanisms works:
   - `suspicious_allow_patterns` removes patterns from the list
   - `duplicate_exclude_patterns` filters file paths correctly
   - `--whitelist` file parameter excludes listed files

4. **Test the fix:**
   ```bash
   cd ~/ci_shared
   # Create a test that reproduces the issue
   # Verify the fix works with the test case above
   ```

5. **Verify in the aws repo:**
   ```bash
   cd /Users/mahrens917/aws
   python -m ci_tools.scripts.unused_module_guard \
     --root . \
     --exclude tests conftest.py __init__.py cost_toolkit/scripts/rds \
     --strict
   # Should pass without warnings after fix
   ```

## Expected Outcome

After the fix, ONE of these should work:

**Option A:** Config-based exclusion
```json
{
  "suspicious_allow_patterns": ["_v2", "_backup"]
}
```

**Option B:** File path filtering
```json
{
  "duplicate_exclude_patterns": ["_backup"]
}
```

**Option C:** Whitelist file
```
tests/test_cost_toolkit_audit_backup_comprehensive.py
tests/test_cost_toolkit_cleanup_backup_disable_comprehensive.py
tests/test_cost_toolkit_common_backup_utils.py
```

Running the guard with `--strict` should:
- ✅ Exit code 0
- ✅ No warnings about the backup test files
- ✅ Still detect actual duplicate issues

## Additional Context

- All 2109 tests in the aws repo pass
- All other CI guards pass (complexity, module_guard, function_size_guard, etc.)
- Only the unused_module_guard --strict fails due to this false positive
- The files were already in the `tests/` directory which is in `--exclude` but that doesn't apply to suspicious duplicates check

## Files to Check in ci_shared

1. `ci_tools/scripts/unused_module_guard.py` - Main implementation
2. Any associated test files
3. Documentation about the whitelist/config system

## Success Criteria

- [ ] Fix is implemented in ci_shared
- [ ] Tests added to prevent regression
- [ ] Verified fix works with the aws repo test case
- [ ] One or more of the three exclusion mechanisms works correctly
- [ ] Documentation updated if needed

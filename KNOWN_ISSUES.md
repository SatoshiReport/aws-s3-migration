# Known Issues

## Unused Module Guard False Positive

**Status:** Known false positive - not a code issue

**Issue:** The `unused_module_guard --strict` reports three legitimate test files as "suspicious duplicates":
- `tests/test_cost_toolkit_audit_backup_comprehensive.py`
- `tests/test_cost_toolkit_cleanup_backup_disable_comprehensive.py`
- `tests/test_cost_toolkit_common_backup_utils.py`

**Why This Occurs:** These files all contain `_backup` in their names because they test different backup-related modules:
- `audit_backup` - tests for AWS Backup audit functionality
- `cleanup_backup_disable` - tests for disabling AWS Backup services
- `common_backup_utils` - tests for shared backup utility functions

They are NOT duplicates - they test completely different modules in different parts of the codebase.

**Root Cause:** Bug in `ci_shared` unused_module_guard - the configuration system does not properly filter suspicious duplicates:
- `suspicious_allow_patterns` in config file: ❌ Does not work
- `duplicate_exclude_patterns` in config file: ❌ Does not work
- `--whitelist` file parameter: ❌ Does not work

All three exclusion mechanisms were tested and none successfully filter the false positives in strict mode.

**Impact:**
- ✅ All 2109 tests pass
- ✅ All other CI checks pass
- ❌ `make check` fails due to this false positive when `--strict` is enabled

**Workaround Options:**
1. Accept the warning (guard passes without `--strict`)
2. Remove `--strict` flag from ci_shared.mk line 136
3. Fix the bug in ci_shared (see prompt below)

**Next Steps:** File issue with ci_shared maintainers to fix the configuration system.

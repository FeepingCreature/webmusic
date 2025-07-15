# Repository Guide for AI Assistants

## Error Handling Philosophy

**DO NOT catch exceptions unless you are absolutely certain they are expected and recoverable.**

### What we want:
- Full stack traces with line numbers
- Detailed error messages showing exactly what went wrong
- Immediate crashes that point to the root cause
- Console output that helps debug the issue

### What we DON'T want:
- Generic error messages like "Error scanning: 'title'"
- Silent failures or swallowed exceptions
- `try/except` blocks that hide the real problem
- Alerts or minimal error reporting

### Examples:

**BAD:**
```python
try:
    metadata = self.extract_metadata(audio_file)
    self.db.add_track(metadata['title'], ...)
except Exception as e:
    print(f"Error scanning {path}: {e}")
    continue
```

**GOOD:**
```python
# Let it crash with full traceback
metadata = self.extract_metadata(audio_file)
self.db.add_track(metadata['title'], ...)
```

**ACCEPTABLE (only if truly expected):**
```python
try:
    audio_file = mutagen.File(path)
except mutagen.MutagenError:
    # This specific error is expected for non-audio files
    return None
```

### 'assert' over 'if'

**BAD:**
```python
if data:
    return data.method()
else:
    return None
```

***GOOD:***
```python
assert data
return data.method()
```

***VERY GOOD:***
```python
def method(data: Type) -> Result:
    return data.method()
```

Every variable should permit only the states that are required.
Errors should be rejected as early as possible in the application flow.

## General Principles

1. **Fail fast and loud** - crashes are better than silent corruption
5. **Assert over if** - keep the possible application states minimal
2. **Preserve stack traces** - they contain crucial debugging information
3. **Only catch specific exceptions** you know how to handle
4. **Let unexpected errors bubble up** to the top level and beyond

Remember: A crash that shows you exactly what's wrong is infinitely more valuable than a program that "handles" errors by hiding them.

#!/bin/bash

# Test script to create non-UTF-8 filenames and test Python encoding behavior

set -e

echo "Creating test directory..."
mkdir -p test_encoding
cd test_encoding

echo "Creating files with various encodings..."

# Create a file with Latin-1 bytes that aren't valid UTF-8
# This creates a filename with byte 0xFF which is invalid UTF-8
echo "test content" > "$(printf 'test_\xff_file.txt')"

# Create a file with some other problematic bytes
echo "test content 2" > "$(printf 'caf\xe9.txt')"  # café in Latin-1

# Create a normal UTF-8 file for comparison
echo "test content 3" > "normal_utf8_file.txt"

echo "Files created:"
ls -la

echo ""
echo "Running Python test..."

python3 << 'EOF'
import os
import sys

print("Python filesystem encoding:", sys.getfilesystemencoding())
print("Python filesystem error handler:", sys.getfilesystemencodeerrors())
print()

# List all files in current directory
print("Files found by os.listdir():")
for filename in os.listdir('.'):
    print(f"  Raw filename: {repr(filename)}")
    
    # Test fsencode/fsdecode round trip
    try:
        decoded = os.fsdecode(filename)
        encoded = os.fsencode(decoded)
        print(f"    fsdecode: {repr(decoded)}")
        print(f"    fsencode: {repr(encoded)}")
        print(f"    Round trip successful: {filename == encoded}")
    except Exception as e:
        print(f"    Error in round trip: {e}")
    
    # Test if we can open the file
    try:
        with open(decoded, 'r') as f:
            content = f.read().strip()
        print(f"    File content: {repr(content)}")
    except Exception as e:
        print(f"    Error reading file: {e}")
    
    print()

# Test storing in SQLite
print("Testing SQLite storage...")
import sqlite3

conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE test (path TEXT)')

for filename in os.listdir(b'.'):
    try:
        conn.execute('INSERT INTO test (path) VALUES (?)', (filename,))
        print(f"  Stored in SQLite: {repr(filename)}")
        
        # Retrieve it back
        result = conn.execute('SELECT path FROM test WHERE path = ?', (filename,)).fetchone()
        if result:
            print(f"    Retrieved: {repr(result[0])}")
            print(f"    Match: {filename == result[0]}")
        else:
            print(f"    Not found in database!")
        with open(result[0], 'r') as f:
            content = f.read().strip()
            print(f"    File content: {repr(content)}")
    except Exception as e:
        print(f"  SQLite error for {repr(filename)}: {e}")
    print()

conn.close()
EOF

echo ""
echo "Cleaning up..."
cd ..
rm -rf test_encoding

echo "Test complete!"

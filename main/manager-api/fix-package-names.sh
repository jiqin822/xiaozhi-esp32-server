#!/bin/bash

# Script to fix package declarations and imports from xiaozhi to pingping
# This matches the directory structure refactoring

cd "$(dirname "$0")"

echo "Fixing package declarations and imports from xiaozhi to pingping..."

# Fix package declarations in Java files
echo "Fixing package declarations..."
find src/main/java -name "*.java" -type f -exec sed -i '' 's/^package xiaozhi\./package pingping./g' {} \;

# Fix import statements in Java files
echo "Fixing import statements..."
find src/main/java -name "*.java" -type f -exec sed -i '' 's/import xiaozhi\./import pingping./g' {} \;

# Fix MyBatis mapper namespace declarations
echo "Fixing MyBatis mapper namespaces..."
find src/main/resources/mapper -name "*.xml" -type f -exec sed -i '' 's/xiaozhi\.modules\./pingping.modules./g' {} \;

# Fix resultType in mapper XML files
find src/main/resources/mapper -name "*.xml" -type f -exec sed -i '' 's/resultType="xiaozhi\./resultType="pingping./g' {} \;

echo ""
echo "Done! Fixed:"
echo "  - Package declarations in Java files"
echo "  - Import statements in Java files"
echo "  - MyBatis mapper namespaces"
echo "  - MyBatis resultType declarations"
echo ""
echo "Please verify the changes and run: mvn clean compile"

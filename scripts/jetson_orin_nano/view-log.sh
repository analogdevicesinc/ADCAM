#!/bin/bash

# Script to view the build log

if [ ! -f build_output.log ]; then
    echo "No build_output.log found. Run ./build.sh first."
    exit 1
fi

case "${1:-tail}" in
    tail)
        echo "Showing last 50 lines (press Ctrl+C to exit):"
        tail -f build_output.log
        ;;
    grep)
        if [ -z "$2" ]; then
            echo "Usage: $0 grep <pattern>"
            exit 1
        fi
        grep -i "$2" build_output.log
        ;;
    errors)
        echo "Searching for errors and warnings:"
        grep -E "(error|warning|failed|Error|Warning|Failed)" build_output.log
        ;;
    all)
        less build_output.log
        ;;
    *)
        echo "Usage: $0 [tail|grep|errors|all]"
        echo "  tail   - Follow the last 50 lines (default)"
        echo "  grep   - Search for a pattern"
        echo "  errors - Show all errors and warnings"
        echo "  all    - View entire log"
        ;;
esac

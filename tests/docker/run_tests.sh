#!/usr/bin/env bash

# Setup colors
if tput setaf 1 &>/dev/null; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    WHITE=$(tput setaf 7)
    RESET=$(tput sgr0)
else
    RED=$'\033[31m'
    GREEN=$'\033[32m'
    YELLOW=$'\033[33m'
    WHITE=$'\033[37m'
    RESET=$'\033[0m'
fi

print_usage() {
    printf '%b\n' "${WHITE}Usage:${RESET} $0 [-f FILE] [OPTIONS]"
    printf '%b\n' ""
    printf '%b\n' "Run ADCAM system tests from CSV configuration."
    printf '%b\n' ""
    printf '%b\n' "Options:"
    printf '%b\n' "  -f, --file FILE    Path to CSV file (required)"
    printf '%b\n' "  -o, --output PATH  Local path for results (default: ./test-results)"
    printf '%b\n' "  -n, --repeat N     Run tests N times (default: 1)"
    printf '%b\n' "  -h, --help         Show help"
    printf '%b\n' ""
    printf '%b\n' "Examples:"
    printf '%b\n' "  $0 -f ../test_csvs/system_test_list.csv"
    printf '%b\n' "  $0 -f ../test_csvs/system_test_list.csv -o ./test-results"
    printf '%b\n' "  $0 -f ../test_csvs/system_test_list.csv -n 3"
}

# Default values
input_file=""
output_path="./test-results"
repeat_count=1

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            print_usage
            exit 0
            ;;
        -f|--file)
            input_file="$2"
            shift 2
            ;;
        -o|--output)
            output_path="$2"
            shift 2
            ;;
        -n|--repeat)
            repeat_count="$2"
            shift 2
            ;;
        *)
            printf '%b\n' "${RED}Unknown option:${RESET} $1"
            print_usage
            exit 1
            ;;
    esac
done

# Validate input file
if [[ -z "$input_file" ]]; then
    printf '%b\n' "${RED}Error:${RESET} CSV file required (-f option)"
    print_usage
    exit 1
fi

if [[ ! -f "$input_file" ]]; then
    printf '%b\n' "${RED}Error:${RESET} File not found: $input_file"
    exit 1
fi

# Create output directory with timestamp
timestamp=$(date -u +"%Y%m%d_%H%M%S")
output_dir="${output_path}_${timestamp}"
mkdir -p "$output_dir"

# Summary file
summary_file="${output_dir}/test_summary.txt"
: > "$summary_file"

# Counters
total_tests=0
passed_tests=0
failed_tests=0
skipped_tests=0

printf '%b\n' "${GREEN}========================================${RESET}"
printf '%b\n' "${GREEN}ADCAM System Test Execution${RESET}"
printf '%b\n' "${GREEN}========================================${RESET}"
printf '%s\n' "CSV File: $input_file"
printf '%s\n' "Output: $output_dir"
printf '%s\n' "Repeat: $repeat_count"
printf '%s\n' "Timestamp: $timestamp"
printf '\n'

# Check if Docker image exists
if ! docker images | grep -q "adcam-test"; then
    printf '%b\n' "${RED}Error:${RESET} Docker image 'adcam-test' not found"
    printf '%s\n' "Please build the Docker image first:"
    printf '%s\n' "  cd tests/docker"
    printf '%s\n' "  bash ./build.sh"
    exit 1
fi

# Read CSV file (skip header and comments)
while IFS=',' read -r testid execute testname testparams; do
    # Skip header and comments
    [[ "$testid" == "TestID" ]] && continue
    [[ "$testid" =~ ^# ]] && continue
    [[ -z "$testid" ]] && continue
    
    # Trim whitespace
    testid=$(echo "$testid" | xargs)
    execute=$(echo "$execute" | xargs)
    testname=$(echo "$testname" | xargs)
    testparams=$(echo "$testparams" | xargs)
    
    # Skip if not marked for execution
    if [[ ! "$execute" =~ ^[Yy]$ ]]; then
        ((skipped_tests++))
        # Only print skip message if testid is not empty (avoid "Skipping: -" for blank lines)
        if [[ -n "$testid" ]]; then
            printf '%b\n' "${YELLOW}Skipping:${RESET} $testid - $testname"
        fi
        continue
    fi
    
    ((total_tests++))
    
    # Run test for each repeat
    for run in $(seq 1 $repeat_count); do
        printf '%b\n' "${WHITE}Running:${RESET} $testid - $testname (run $run/$repeat_count)"
        
        test_log="${output_dir}/${testid}_run${run}.log"
        test_json="${output_dir}/${testid}_run${run}.json"
        
        # Build command - check if it's a relative path (example binary) or test binary
        if [[ "$testname" == ../* ]] || [[ "$testname" == /* ]]; then
            # Relative or absolute path (e.g., ../../examples/first-frame)
            test_cmd="/workspace/project/build/tests/bin/$testname"
        else
            # Test binary in tests/bin/
            test_cmd="/workspace/project/build/tests/bin/$testname"
        fi
        
        if [[ -n "$testparams" ]]; then
            test_cmd="$test_cmd $testparams"
        fi
        
        # Add GoogleTest JSON output only if it's a GoogleTest binary (not example binaries)
        if [[ "$testname" != ../* ]] && [[ "$testname" != /* ]]; then
            test_cmd="$test_cmd --gtest_output=json:$test_json"
        fi
        
        # Run test in Docker with hardware access
        if docker run --rm --privileged \
            --device=/dev/video0 \
            --device=/dev/video1 \
            --device=/dev/video2 \
            --device=/dev/video3 \
            --device=/dev/media0 \
            --device=/dev/media1 \
            --device=/dev/i2c-0 \
            --device=/dev/i2c-1 \
            --device=/dev/i2c-2 \
            -v "$(pwd)/test-results:/workspace/test-results" \
            -v "$(pwd)/test-logs:/workspace/test-logs" \
            -v "$(realpath ../../libs 2>/dev/null || echo /tmp):/workspace/libs:ro" \
            -e "GTEST_COLOR=1" \
            -e "LD_LIBRARY_PATH=/workspace/libs:/workspace/project/build/lib" \
            adcam-test:latest \
            bash -c "$test_cmd" > "$test_log" 2>&1; then
            
            printf '%b\n' "${GREEN}✓ PASSED${RESET}"
            echo "$testid,$testname,run_${run},Passed" >> "$summary_file"
            ((passed_tests++))
        else
            exit_code=$?
            printf '%b\n' "${RED}✗ FAILED (exit code: $exit_code)${RESET}"
            echo "$testid,$testname,run_${run},Failed: exit code $exit_code" >> "$summary_file"
            ((failed_tests++))
            
            # Show last 20 lines of log for quick diagnosis
            printf '%b\n' "${YELLOW}Last 20 lines of log:${RESET}"
            tail -n 20 "$test_log" | sed 's/^/  /'
        fi
    done
    
    printf '\n'
done < "$input_file"

# Print summary
printf '%b\n' "${GREEN}========================================${RESET}"
printf '%b\n' "${GREEN}Test Summary${RESET}"
printf '%b\n' "${GREEN}========================================${RESET}"
printf '%s\n' "Total Tests Run: $total_tests"
printf '%b\n' "${GREEN}Passed: $passed_tests${RESET}"
printf '%b\n' "${RED}Failed: $failed_tests${RESET}"
printf '%b\n' "${YELLOW}Skipped: $skipped_tests${RESET}"
printf '%s\n' ""
printf '%s\n' "Detailed results saved to: $output_dir"
printf '%s\n' "Summary file: $summary_file"

# Calculate pass rate
if [ $total_tests -gt 0 ]; then
    pass_rate=$((passed_tests * 100 / total_tests))
    printf '%s\n' "Pass Rate: ${pass_rate}%"
fi

printf '\n'

# Exit with failure if any tests failed
if [ $failed_tests -gt 0 ]; then
    printf '%b\n' "${RED}Some tests failed. Check logs for details.${RESET}"
    exit 1
fi

printf '%b\n' "${GREEN}All tests passed!${RESET}"
exit 0

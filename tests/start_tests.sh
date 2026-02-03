#!/usr/bin/env bash
set -euo pipefail

# ADCAM System Test Wrapper
# Main entry point for running ADCAM system tests in Docker

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

# Default values
repeat_count=1
csv_file=""
output_path=""
force_build=false
force_cleanup=false
jobs=6
git_branch=""
nvidia_build=false

print_usage() {
    cat << EOF
${WHITE}ADCAM System Test Wrapper${RESET}

Usage: $0 -f|--file CSV_FILE -o|--output PATH [OPTIONS]

Run ADCAM system tests using CSV configuration in Docker container.

${WHITE}Required Options:${RESET}
    -f, --file CSV_FILE    CSV test list file (required)
    -o, --output PATH      Output folder for results (required)

${WHITE}Optional Parameters:${RESET}
    -r, --repeat COUNT     Number of times to run tests (default: 1)
    -j, --jobs COUNT       Parallel build jobs (default: 6)
    --branch NAME          Git branch to checkout and build (default: current)
    --nvidia               Build for NVIDIA Jetson target (default: off)
    -b, --build            Force rebuild of Docker container
    -c, --cleanup          Cleanup Docker container on exit
    -h, --help             Show this help message

${WHITE}Examples:${RESET}
    $0 -f test_csvs/system_test_list.csv -o ~/test-results
    $0 -f test_csvs/system_test_list.csv -o ./results --nvidia
    $0 -f test_csvs/system_test_list.csv -o ./results -b -c
    $0 -f test_csvs/system_test_list.csv -o ./results -r 3 -j 8
    $0 -f test_csvs/system_test_list.csv -o ./results --branch feature-xyz --nvidia

${WHITE}Prerequisites:${RESET}
    - Docker installed and running
    - ToFi libraries at ../libs/ (libtofi_compute.so, libtofi_config.so)
    - GoogleTest installed in Docker image

${WHITE}CSV Test Configuration:${RESET}
    The CSV file should contain test configurations with columns:
    - TestID: Unique identifier (e.g., SY000001)
    - Execute: Y/y to run, N/n to skip
    - TestName: Test executable name
    - TestParameters: Command-line arguments

${WHITE}Output:${RESET}
    Results are saved to <output_path>_<timestamp>/
    - Individual test logs: <testid>_run<N>.log
    - JSON test results: <testid>_run<N>.json
    - Summary: test_summary.txt
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--repeat)
            repeat_count="$2"
            shift 2
            ;;
        -j|--jobs)
            jobs="$2"
            shift 2
            ;;
        --branch)
            git_branch="$2"
            shift 2
            ;;
        --nvidia)
            nvidia_build=true
            shift
            ;;
        -f|--file)
            csv_file="$2"
            shift 2
            ;;
        -o|--output)
            output_path="$2"
            shift 2
            ;;
        -b|--build)
            force_build=true
            shift
            ;;
        -c|--cleanup)
            force_cleanup=true
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            printf '%b\n' "${RED}Unknown option:${RESET} $1"
            print_usage
            exit 1
            ;;
    esac
done

# Validate arguments
if [[ -z "$csv_file" ]]; then
    printf '%b\n' "${RED}Error:${RESET} CSV file is required. Use -f or --file"
    print_usage
    exit 1
fi

if [[ -z "$output_path" ]]; then
    printf '%b\n' "${RED}Error:${RESET} Output path is required. Use -o or --output"
    print_usage
    exit 1
fi

# Check if CSV file exists
if [[ ! -f "$csv_file" ]]; then
    printf '%b\n' "${RED}Error:${RESET} CSV file not found: $csv_file"
    exit 1
fi

# Convert to absolute paths
csv_file="$(realpath "$csv_file")"
output_path="$(realpath "$output_path" 2>/dev/null || echo "$output_path")"

# Get script directory
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

printf '%b\n' "${GREEN}========================================${RESET}"
printf '%b\n' "${GREEN}ADCAM System Test Execution${RESET}"
printf '%b\n' "${GREEN}========================================${RESET}"
printf '%s\n' "CSV File: $csv_file"
printf '%s\n' "Output: $output_path"
printf '%s\n' "Repeat: $repeat_count"
printf '%s\n' "Build Jobs: $jobs"
printf '\n'

# Check for ToFi libraries
libs_dir="$script_dir/../libs"
if [[ ! -d "$libs_dir" ]]; then
    libs_dir="$(realpath "$script_dir/../../libs" 2>/dev/null || echo "")"
fi

if [[ -d "$libs_dir" && -f "$libs_dir/libtofi_compute.so" ]]; then
    printf '%b\n' "${GREEN}✓ ToFi libraries found at:${RESET} $libs_dir"
else
    printf '%b\n' "${YELLOW}⚠ Warning: ToFi libraries not found${RESET}"
    printf '%s\n' "Expected location: $script_dir/../../libs/"
    printf '%s\n' "Required files:"
    printf '%s\n' "  - libtofi_compute.so"
    printf '%s\n' "  - libtofi_config.so"
    printf '\n'
fi

# Enter docker directory
cd "$script_dir/docker"

# Build if requested or image doesn't exist
if $force_build || ! docker images | grep -q "adcam-test"; then
    printf '%b\n' "${GREEN}Building Docker image...${RESET}"
    
    # Build command with optional branch and nvidia flag
    build_cmd="bash ./build.sh -j \"$jobs\""
    if [[ -n "$git_branch" ]]; then
        build_cmd="$build_cmd --branch \"$git_branch\""
    fi
    if $nvidia_build; then
        build_cmd="$build_cmd --nvidia"
    fi
    
    eval "$build_cmd"
    
    if [ $? -ne 0 ]; then
        printf '%b\n' "${RED}✗ Docker build failed${RESET}"
        exit 1
    fi
    printf '\n'
else
    printf '%b\n' "${GREEN}✓ Using existing Docker image${RESET}"
    printf '\n'
fi

# Run tests
printf '%b\n' "${GREEN}Running tests...${RESET}"
printf '\n'

bash ./run_tests.sh -f "$csv_file" -o "$output_path" -n "$repeat_count"
test_exit_code=$?

# Cleanup if requested
if $force_cleanup; then
    printf '\n'
    printf '%b\n' "${GREEN}Cleaning up Docker resources...${RESET}"
    docker rmi adcam-test:latest 2>/dev/null || true
fi

printf '\n'
if [ $test_exit_code -eq 0 ]; then
    printf '%b\n' "${GREEN}========================================${RESET}"
    printf '%b\n' "${GREEN}✓ Test execution complete!${RESET}"
    printf '%b\n' "${GREEN}========================================${RESET}"
else
    printf '%b\n' "${RED}========================================${RESET}"
    printf '%b\n' "${RED}✗ Test execution failed${RESET}"
    printf '%b\n' "${RED}========================================${RESET}"
fi

printf '%s\n' "Results available at: $output_path"
printf '\n'

exit $test_exit_code

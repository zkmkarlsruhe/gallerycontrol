#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8000"
ANEL_BASE="http://localhost:8001"

echo "================================"
echo "MuTech Control System - Test Suite"
echo "================================"
echo ""

# Function to test endpoint
test_endpoint() {
    local method=$1
    local url=$2
    local expected_code=$3
    local description=$4

    echo -n "Testing: $description... "

    response=$(curl -s -w "\n%{http_code}" -X $method "$url" 2>/dev/null || echo "000")
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "$expected_code" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $http_code)"
        return 0
    else
        echo -e "${RED}FAIL${NC} (Expected $expected_code, got $http_code)"
        echo "Response: $body"
        return 1
    fi
}

# Function to test JSON endpoint
test_json_endpoint() {
    local method=$1
    local url=$2
    local data=$3
    local expected_code=$4
    local description=$5

    echo -n "Testing: $description... "

    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X $method "$url" \
            -H "Content-Type: application/json" 2>/dev/null || echo "000")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$url" \
            -H "Content-Type: application/json" \
            -d "$data" 2>/dev/null || echo "000")
    fi

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "$expected_code" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $http_code)"
        echo "$body"
        return 0
    else
        echo -e "${RED}FAIL${NC} (Expected $expected_code, got $http_code)"
        echo "Response: $body"
        return 1
    fi
}

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

# Test 1: Health checks
echo "=== Basic Health Checks ==="
if test_endpoint "GET" "$API_BASE/health" "200" "Main service health"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

if test_endpoint "GET" "$API_BASE/" "200" "Root endpoint"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

if test_endpoint "GET" "$API_BASE/info" "200" "System info endpoint"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

echo ""

# Test 2: Admin API - Exhibitions
echo "=== Admin API - Exhibitions ==="

# Create exhibition
exhibition_response=$(test_json_endpoint "POST" "$API_BASE/api/admin/exhibitions" \
    '{"name":"Test Exhibition","enabled":true}' \
    "201" "Create exhibition" || echo "")

if [ -n "$exhibition_response" ]; then
    ((TESTS_PASSED++))
    EXHIBITION_ID=$(echo "$exhibition_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    echo "Created exhibition ID: $EXHIBITION_ID"
else
    ((TESTS_FAILED++))
    echo -e "${RED}Cannot continue without exhibition ID${NC}"
    exit 1
fi

# List exhibitions
if test_endpoint "GET" "$API_BASE/api/admin/exhibitions" "200" "List exhibitions"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

echo ""

# Test 3: Admin API - Artworks
echo "=== Admin API - Artworks ==="

# Create artwork
artwork_response=$(test_json_endpoint "POST" "$API_BASE/api/admin/artworks" \
    "{\"exhibition_id\":\"$EXHIBITION_ID\",\"name\":\"Test Artwork\",\"enabled\":true}" \
    "201" "Create artwork" || echo "")

if [ -n "$artwork_response" ]; then
    ((TESTS_PASSED++))
    ARTWORK_ID=$(echo "$artwork_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    echo "Created artwork ID: $ARTWORK_ID"
else
    ((TESTS_FAILED++))
    echo -e "${RED}Cannot continue without artwork ID${NC}"
    exit 1
fi

# List artworks
if test_endpoint "GET" "$API_BASE/api/admin/artworks" "200" "List artworks"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

echo ""

# Test 4: Admin API - Devices
echo "=== Admin API - Devices ==="

# Create device (shell type for testing - doesn't require real hardware)
device_response=$(test_json_endpoint "POST" "$API_BASE/api/admin/devices" \
    "{\"artwork_id\":\"$ARTWORK_ID\",\"name\":\"Test Shell Device\",\"device_type\":\"shell\",\"host\":\"localhost\",\"enabled\":true,\"automation_enabled\":true,\"exclude_from_auto_onoff\":false,\"config\":{\"commands\":{\"on\":{\"cmd\":\"echo on\",\"timeout\":5},\"off\":{\"cmd\":\"echo off\",\"timeout\":5},\"status\":{\"cmd\":\"echo status\",\"timeout\":5,\"onPattern\":\"on\",\"offPattern\":\"off\"}}}}" \
    "201" "Create device" || echo "")

if [ -n "$device_response" ]; then
    ((TESTS_PASSED++))
    DEVICE_ID=$(echo "$device_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
    echo "Created device ID: $DEVICE_ID"
else
    ((TESTS_FAILED++))
fi

# List devices
if test_endpoint "GET" "$API_BASE/api/admin/devices" "200" "List devices"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

echo ""

# Test 5: State API
echo "=== State API ==="

if test_endpoint "GET" "$API_BASE/api/state/exhibitions" "200" "Get all exhibitions state"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

if [ -n "$EXHIBITION_ID" ]; then
    if test_endpoint "GET" "$API_BASE/api/state/exhibition/$EXHIBITION_ID" "200" "Get exhibition state"; then
        ((TESTS_PASSED++))
    else
        ((TESTS_FAILED++))
    fi
fi

if [ -n "$DEVICE_ID" ]; then
    if test_endpoint "GET" "$API_BASE/api/state/device/$DEVICE_ID" "200" "Get device state"; then
        ((TESTS_PASSED++))
    else
        ((TESTS_FAILED++))
    fi
fi

echo ""

# Test 6: Control API
echo "=== Control API ==="

if [ -n "$DEVICE_ID" ]; then
    echo -e "${YELLOW}Note: Control tests may fail if device is not reachable${NC}"

    # These might fail if the shell command doesn't work
    test_endpoint "POST" "$API_BASE/api/control/device/$DEVICE_ID/on" "200" "Turn device ON" || true
    test_endpoint "POST" "$API_BASE/api/control/device/$DEVICE_ID/off" "200" "Turn device OFF" || true
fi

echo ""

# Test 7: Fast Lane API
echo "=== Fast Lane API ==="

if [ -n "$DEVICE_ID" ]; then
    echo -e "${YELLOW}Note: Fast lane tests may fail if device is not reachable${NC}"

    test_endpoint "POST" "$API_BASE/api/fast/device/$DEVICE_ID/on" "200" "Fast lane ON" || true
    test_endpoint "POST" "$API_BASE/api/fast/device/$DEVICE_ID/off" "200" "Fast lane OFF" || true
    test_endpoint "GET" "$API_BASE/api/fast/device/$DEVICE_ID/state" "200" "Fast lane state query" || true
fi

echo ""

# Test 8: Config reload
echo "=== Configuration Management ==="

if test_endpoint "POST" "$API_BASE/api/admin/config/reload" "200" "Config reload"; then
    ((TESTS_PASSED++))
else
    ((TESTS_FAILED++))
fi

echo ""

# Test 9: Cleanup
echo "=== Cleanup ==="

if [ -n "$DEVICE_ID" ]; then
    if test_endpoint "DELETE" "$API_BASE/api/admin/devices/$DEVICE_ID" "204" "Delete device"; then
        ((TESTS_PASSED++))
    else
        ((TESTS_FAILED++))
    fi
fi

if [ -n "$ARTWORK_ID" ]; then
    if test_endpoint "DELETE" "$API_BASE/api/admin/artworks/$ARTWORK_ID" "204" "Delete artwork"; then
        ((TESTS_PASSED++))
    else
        ((TESTS_FAILED++))
    fi
fi

if [ -n "$EXHIBITION_ID" ]; then
    if test_endpoint "DELETE" "$API_BASE/api/admin/exhibitions/$EXHIBITION_ID" "204" "Delete exhibition"; then
        ((TESTS_PASSED++))
    else
        ((TESTS_FAILED++))
    fi
fi

echo ""

# Test 10: ANEL Runner (optional)
echo "=== ANEL Runner Health Check (Optional) ==="
echo -e "${YELLOW}Note: This may fail if ANEL runner is not accessible or uses different network mode${NC}"

test_endpoint "GET" "$ANEL_BASE/health" "200" "ANEL runner health" || echo -e "${YELLOW}ANEL runner not accessible (this is normal if network_mode: host)${NC}"

echo ""

# Summary
echo "================================"
echo "Test Summary"
echo "================================"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi

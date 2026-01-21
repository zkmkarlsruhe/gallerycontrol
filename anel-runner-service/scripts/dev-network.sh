#!/bin/bash
# Development Network Setup for ANEL Runner
#
# This script helps set up networking for development and testing
# when the ANEL devices are on a separate network segment.
#
# Usage:
#   ./scripts/dev-network.sh create  - Create macvlan network
#   ./scripts/dev-network.sh delete  - Delete macvlan network
#   ./scripts/dev-network.sh status  - Show network status

set -e

# Configuration - adjust these for your environment
ANEL_SUBNET="${ANEL_SUBNET:-192.168.50.0/24}"
ANEL_GATEWAY="${ANEL_GATEWAY:-192.168.50.1}"
ANEL_RUNNER_IP="${ANEL_RUNNER_IP:-192.168.50.100}"
PARENT_INTERFACE="${PARENT_INTERFACE:-eth0}"
NETWORK_NAME="anel-macvlan"

print_usage() {
    echo "ANEL Runner Development Network Setup"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  create    Create macvlan network for ANEL access"
    echo "  delete    Delete the macvlan network"
    echo "  status    Show current network status"
    echo "  test      Test connectivity to an ANEL device"
    echo ""
    echo "Environment variables:"
    echo "  ANEL_SUBNET        Network subnet (default: $ANEL_SUBNET)"
    echo "  ANEL_GATEWAY       Gateway IP (default: $ANEL_GATEWAY)"
    echo "  ANEL_RUNNER_IP     IP for runner container (default: $ANEL_RUNNER_IP)"
    echo "  PARENT_INTERFACE   Host interface on ANEL network (default: $PARENT_INTERFACE)"
    echo ""
    echo "Example:"
    echo "  PARENT_INTERFACE=ens192 ANEL_SUBNET=10.0.50.0/24 $0 create"
}

create_network() {
    echo "Creating macvlan network: $NETWORK_NAME"
    echo "  Subnet: $ANEL_SUBNET"
    echo "  Gateway: $ANEL_GATEWAY"
    echo "  Parent interface: $PARENT_INTERFACE"
    echo ""

    # Check if parent interface exists
    if ! ip link show "$PARENT_INTERFACE" &>/dev/null; then
        echo "ERROR: Parent interface $PARENT_INTERFACE does not exist"
        echo ""
        echo "Available interfaces:"
        ip link show | grep -E "^[0-9]+:" | awk '{print $2}' | tr -d ':'
        exit 1
    fi

    # Check if network already exists
    if docker network inspect "$NETWORK_NAME" &>/dev/null; then
        echo "Network $NETWORK_NAME already exists"
        docker network inspect "$NETWORK_NAME" --format '{{.IPAM.Config}}'
        exit 0
    fi

    # Create macvlan network
    docker network create \
        --driver macvlan \
        --subnet="$ANEL_SUBNET" \
        --gateway="$ANEL_GATEWAY" \
        --opt parent="$PARENT_INTERFACE" \
        "$NETWORK_NAME"

    echo ""
    echo "Network created successfully!"
    echo ""
    echo "To run the ANEL runner with this network:"
    echo "  docker compose -f docker-compose.yml -f docker-compose.dev.yml up"
    echo ""
    echo "The runner will have IP: $ANEL_RUNNER_IP"
}

delete_network() {
    echo "Deleting macvlan network: $NETWORK_NAME"

    if docker network inspect "$NETWORK_NAME" &>/dev/null; then
        # Stop any containers using this network
        containers=$(docker network inspect "$NETWORK_NAME" --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || true)
        if [ -n "$containers" ]; then
            echo "Stopping containers using this network: $containers"
            for container in $containers; do
                docker stop "$container" 2>/dev/null || true
            done
        fi

        docker network rm "$NETWORK_NAME"
        echo "Network deleted"
    else
        echo "Network $NETWORK_NAME does not exist"
    fi
}

show_status() {
    echo "ANEL Network Status"
    echo "==================="
    echo ""

    echo "Docker networks:"
    docker network ls --filter name=anel

    echo ""
    echo "Host interfaces:"
    ip addr show | grep -E "^[0-9]+:|inet " | head -20

    echo ""
    if docker network inspect "$NETWORK_NAME" &>/dev/null; then
        echo "Macvlan network details:"
        docker network inspect "$NETWORK_NAME" --format '
  Name: {{.Name}}
  Driver: {{.Driver}}
  Subnet: {{range .IPAM.Config}}{{.Subnet}}{{end}}
  Gateway: {{range .IPAM.Config}}{{.Gateway}}{{end}}
  Parent: {{index .Options "parent"}}
  Containers: {{range .Containers}}{{.Name}} ({{.IPv4Address}}) {{end}}'
    else
        echo "Macvlan network not created"
    fi
}

test_connectivity() {
    local target_ip="${1:-}"

    if [ -z "$target_ip" ]; then
        echo "Usage: $0 test <anel-device-ip>"
        exit 1
    fi

    echo "Testing connectivity to ANEL device at $target_ip"
    echo ""

    # Test UDP port 9975 (command port)
    echo "Testing UDP port 9975 (command port)..."
    if nc -zu -w2 "$target_ip" 9975 2>/dev/null; then
        echo "  Port 9975: OPEN"
    else
        echo "  Port 9975: Cannot verify (UDP is connectionless)"
    fi

    # Send "wer da?" query and listen for response
    echo ""
    echo "Sending 'wer da?' query..."
    echo -n "wer da?" | nc -u -w2 "$target_ip" 9975 &
    sleep 1

    # Check if we can bind to receive port
    echo ""
    echo "Checking if port 9977 is available for listening..."
    if nc -zlu 9977 2>/dev/null; then
        echo "  Port 9977: Available"
    else
        echo "  Port 9977: May be in use or restricted"
    fi

    echo ""
    echo "Note: ANEL devices broadcast status on UDP port 9977."
    echo "You may need to run tcpdump to see broadcasts:"
    echo "  sudo tcpdump -i $PARENT_INTERFACE udp port 9977"
}

# Main
case "${1:-}" in
    create)
        create_network
        ;;
    delete)
        delete_network
        ;;
    status)
        show_status
        ;;
    test)
        test_connectivity "$2"
        ;;
    *)
        print_usage
        exit 1
        ;;
esac

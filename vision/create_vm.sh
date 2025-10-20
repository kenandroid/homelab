#!/bin/bash

# Proxmox VM Creation Script for Ubuntu Server
# This script creates a VM with specified resources

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Function to find next available VM ID
find_next_vm_id() {
    local id=$STARTING_ID
    local max_id=9999
    
    while [[ $id -le $max_id ]]; do
        # Check if ID is used by VM or LXC
        if ! qm status $id &> /dev/null && ! pct status $id &> /dev/null; then
            echo $id
            return 0
        fi
        ((id++))
    done
    
    error "No available VM ID found in range $STARTING_ID-$max_id"
    exit 1
}

# VM Configuration Variables
VM_NAME="vision"               # Change this to your desired VM name
TEMPLATE_NAME="ubuntu-template" # Template to clone from
STORAGE_POOL="local-lvm"       # Change this to your storage pool
MEMORY="4096"                  # 4GB RAM
CORES="2"                      # 2 vCPUs
DISK_SIZE="25G"                # 25GB storage
NETWORK_BRIDGE="vmbr0"         # Network bridge
STARTING_ID="100"              # Starting ID to search from

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
   exit 1
fi

# Find next available VM ID
log "Finding next available VM ID..."
VM_ID=$(find_next_vm_id)
log "Using VM ID: $VM_ID"

# Check if template exists
log "Checking if template exists..."
if ! qm list | grep -q "$TEMPLATE_NAME"; then
    error "Template '$TEMPLATE_NAME' not found"
    error "Available templates:"
    qm list | grep -E "(TEMPLATE|template)" || echo "No templates found"
    exit 1
fi

# Get template ID
TEMPLATE_ID=$(qm list | grep "$TEMPLATE_NAME" | awk '{print $1}')
log "Found template: $TEMPLATE_NAME (ID: $TEMPLATE_ID)"

log "Starting VM creation process..."
log "VM ID: $VM_ID"
log "VM Name: $VM_NAME"
log "Template: $TEMPLATE_NAME (ID: $TEMPLATE_ID)"
log "Memory: ${MEMORY}MB"
log "Cores: $CORES"
log "Disk Size: $DISK_SIZE"
log "Storage Pool: $STORAGE_POOL"
log "Network Bridge: $NETWORK_BRIDGE"

# Clone VM from template
log "Cloning VM from template..."
qm clone $TEMPLATE_ID $VM_ID --name "$VM_NAME" --full

# Configure the cloned VM
log "Configuring VM resources..."
qm set $VM_ID --memory $MEMORY
qm set $VM_ID --cores $CORES
qm set $VM_ID --net0 virtio,bridge=$NETWORK_BRIDGE

# Resize disk if needed
log "Checking disk size..."
CURRENT_DISK_SIZE=$(qm config $VM_ID | grep "scsi0:" | sed 's/.*size=\([^,]*\).*/\1/')
if [[ "$CURRENT_DISK_SIZE" != "$DISK_SIZE" ]]; then
    log "Resizing disk from $CURRENT_DISK_SIZE to $DISK_SIZE..."
    qm resize $VM_ID scsi0 $DISK_SIZE
fi

# Enable QEMU Guest Agent
log "Enabling QEMU Guest Agent..."
qm set $VM_ID --agent enabled=1

# Set CPU type for better performance
log "Setting CPU type..."
qm set $VM_ID --cpu host

# Enable memory ballooning
log "Enabling memory ballooning..."
qm set $VM_ID --balloon 0

# Set up serial console
log "Setting up serial console..."
qm set $VM_ID --serial0 socket

# Display VM configuration
log "VM created successfully!"
info "VM Configuration:"
info "  ID: $VM_ID"
info "  Name: $VM_NAME"
info "  Memory: ${MEMORY}MB"
info "  Cores: $CORES"
info "  Disk: $DISK_SIZE"
info "  Network: $NETWORK_BRIDGE"
info "  Template: $TEMPLATE_NAME (ID: $TEMPLATE_ID)"

warning "Next steps:"
warning "  1. Start the VM: qm start $VM_ID"
warning "  2. Access via Proxmox web interface or SSH"
warning "  3. Configure network settings if needed"
warning "  4. Update system packages: sudo apt update && sudo apt upgrade"

log "VM creation completed!"

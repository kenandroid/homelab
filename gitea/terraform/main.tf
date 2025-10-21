terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
      version = "~> 2.9"
    }
  }
}

provider "proxmox" {
  pm_api_url      = var.proxmox_api_url
  pm_user         = var.proxmox_username
  pm_password     = var.proxmox_password
  pm_tls_insecure = true
}

resource "proxmox_vm_qemu" "gitea" {
  name        = "gitea"
  target_node = "jarvis"
  
  # Clone from template
  clone = "ubuntu-template"
  
  # VM Configuration
  cores   = 2
  memory  = 4096
  sockets = 1
  
  # Storage
  disk {
    slot    = 0
    size    = "25G"
    type    = "scsi"
    storage = "local-lvm"
    iothread = 1
  }
  
  # Network
  network {
    model  = "virtio"
    bridge = "vmbr0"
  }
  
  # Enable QEMU guest agent
  agent = 1
  
  # Cloud-init settings for DHCP
  ciuser     = "ubuntu"
  cipassword = "ubuntu"  # Change this to a secure password
  
  # Additional settings
  onboot = true
  scsihw = "virtio-scsi-pci"
  
  # Lifecycle settings
  lifecycle {
    ignore_changes = [
      network,
    ]
  }
}

output "vm_id" {
  description = "The ID of the created VM"
  value       = proxmox_vm_qemu.gitea.vmid
}

output "vm_name" {
  description = "The name of the created VM"
  value       = proxmox_vm_qemu.gitea.name
}

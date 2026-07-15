# Illustrative only. NOT applied, NOT part of the demo - a single azurerm
# resource block to show IaC intent; the rest of the production story is
# prose in ARCHITECTURE_MAPPING.md (Phases.md Phase 7).
#
# This is the production masking key store: Architecture.md section 6 says
# production replaces this demo's fixed application-level salt (see
# pipeline/silver.py MASK_SALT) with a keyed HMAC, key held here, rotated
# per policy - never an application constant.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_key_vault" "lendinglens_masking_key" {
  name                = "lendinglens-mask-kv"
  location            = "australiaeast"
  resource_group_name = "lendinglens-prod" # illustrative - not a real resource group
  tenant_id           = "00000000-0000-0000-0000-000000000000" # placeholder
  sku_name            = "standard"
}

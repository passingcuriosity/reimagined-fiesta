terraform {
  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "2.1.2"
    }
  }
}

variable "aiven_api_token" {
  type = string
}

variable "aiven_cloud" {
  type = string
}

variable "aiven_project" {
  type        = string
  description = "Aiven project ID"
}

provider "aiven" {
  api_token = var.aiven_api_token
}

resource "aiven_project" "test" {
  project = var.aiven_project
}

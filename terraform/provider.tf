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

output "schema_registry_uri" {
  value = "https://${data.aiven_service_user.kafka_admin.username}:${data.aiven_service_user.kafka_admin.password}@${data.aiven_service_component.schema_registry.host}:${data.aiven_service_component.schema_registry.port}"
}

output "bootstrap_servers" {
  value = aiven_kafka.kafka.service_uri
}

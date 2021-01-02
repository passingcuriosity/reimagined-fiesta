resource "aiven_kafka" "kafka" {
  project                 = aiven_project.test.project
  cloud_name              = var.aiven_cloud
  plan                    = "startup-2"
  service_name            = "kafka-3865ae05"
  maintenance_window_dow  = "friday"
  maintenance_window_time = "07:18:26"
  default_acl             = false

  kafka_user_config {
    schema_registry = true
    kafka_version   = "2.6"
    kafka {
      group_max_session_timeout_ms = 300000
    }

    kafka_authentication_methods {
      sasl = true
    }
  }
}

resource "aiven_service" "pg" {
  project      = aiven_project.test.id
  cloud_name   = var.aiven_cloud
  plan         = "hobbyist"
  service_name = "pg-f65aab9"
  service_type = "pg"
}

resource "aiven_kafka_connect" "kafka_connect" {
  project                 = aiven_project.test.project
  cloud_name              = var.aiven_cloud
  plan                    = "startup-4"
  service_name            = "kafkaconnect-291657d5"
  maintenance_window_dow  = "wednesday"
  maintenance_window_time = "02:32:27"
}

resource "aiven_service_integration" "i1" {
  project                  = aiven_project.test.project
  integration_type         = "kafka_connect"
  source_service_name      = aiven_kafka.kafka.service_name
  destination_service_name = aiven_kafka_connect.kafka_connect.service_name
}

data "aiven_service_component" "schema_registry" {
  project      = aiven_kafka.kafka.project
  service_name = aiven_kafka.kafka.service_name
  component    = "schema_registry"
  route        = "dynamic"
}

data "aiven_service_user" "kafka_admin" {
  project      = aiven_project.test.project
  service_name = aiven_kafka.kafka.service_name

  username = "avnadmin"
}

data "aiven_service_user" "pg_admin" {
  project      = aiven_project.test.project
  service_name = aiven_service.pg.service_name

  username = "avnadmin"
}

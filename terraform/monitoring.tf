resource "aiven_kafka_topic" "monitoring" {
  project      = aiven_project.test.project
  service_name = aiven_kafka.kafka.service_name
  topic_name   = "monitoring"
  partitions   = 3
  replication  = 3
}

resource "aiven_database" "monitoring" {
  project       = aiven_project.test.project
  service_name  = aiven_service.pg.service_name
  database_name = "monitoring"
}

resource "aiven_kafka_connector" "pg-monitoring" {
  project        = aiven_project.test.project
  service_name   = aiven_kafka_connect.kafka_connect.service_name
  connector_name = "monitoring"

  config = {
    "name"      = "monitoring"
    "tasks.max" = 3
    "topics"    = aiven_kafka_topic.monitoring.topic_name

    "connector.class" = "io.aiven.connect.jdbc.JdbcSinkConnector"

    "connection.url"        = "jdbc:postgresql://${aiven_service.pg.service_host}:${aiven_service.pg.service_port}/${aiven_database.monitoring.database_name}?sslmode=require"
    "connection.user"       = data.aiven_service_user.pg_admin.username
    "connection.password"   = data.aiven_service_user.pg_admin.password
    "auto.create"           = true
    "auto.evolve"           = true
    "insert.mode"           = "insert"
    "pk.mode"               = "none"
    "sql.quote.identifiers" = "true"
    "table.name.format"     = "monitoring"

    "connection.user"                               = "avnadmin"
    "key.converter"                                 = "org.apache.kafka.connect.storage.StringConverter"
    "value.converter"                               = "io.confluent.connect.avro.AvroConverter"
    "value.converter.basic.auth.credentials.source" = "USER_INFO"
    "value.converter.basic.auth.user.info"          = "${data.aiven_service_user.kafka_admin.username}:${data.aiven_service_user.kafka_admin.password}"
    "value.converter.schema.registry.url"           = "https://${data.aiven_service_component.schema_registry.host}:${data.aiven_service_component.schema_registry.port}"
  }
}

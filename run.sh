set -eu

terraform_output() {
    cd terraform > /dev/null
    terraform output -no-color "$1" | sed -Ee 's/(^"|"$)//g'
    cd - > /dev/null
}

bootstrap_servers="$(terraform_output bootstrap_servers)"
schema_registry_uri="$(terraform_output schema_registry_uri)"

latency-logger \
    --verbose \
    --bootstrap-servers "$bootstrap_servers" \
    --schema-registry "$schema_registry_uri" \
    "${@}"

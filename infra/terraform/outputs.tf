output "service_url" {
  description = "App Runner service URL."
  value       = aws_apprunner_service.vertical_service.service_url
}

output "health_url" {
  description = "Health endpoint for smoke tests and demos."
  value       = "https://${aws_apprunner_service.vertical_service.service_url}/health"
}

output "metrics_url" {
  description = "Prometheus metrics endpoint for demos."
  value       = "https://${aws_apprunner_service.vertical_service.service_url}/metrics"
}

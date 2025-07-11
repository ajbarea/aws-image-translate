# terraform/frontend.tf

resource "aws_s3_bucket" "frontend_hosting" {
  bucket        = var.frontend_bucket_name
  force_destroy = true

  tags = {
    Name        = var.frontend_bucket_name
    Environment = var.environment
    Purpose     = "website-hosting"
  }
}

resource "aws_s3_bucket_website_configuration" "frontend_hosting" {
  bucket = aws_s3_bucket.frontend_hosting.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend_hosting" {
  bucket                  = aws_s3_bucket.frontend_hosting.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "frontend_hosting" {
  bucket     = aws_s3_bucket.frontend_hosting.id
  depends_on = [aws_s3_bucket_public_access_block.frontend_hosting]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend_hosting.arn}/*"
      },
    ]
  })
}

locals {
  all_frontend_files = fileset(var.frontend_path, "**/*")
  frontend_files     = [for f in local.all_frontend_files : f if f != "js/config.js"]

  mime_types = {
    "html" = "text/html",
    "css"  = "text/css",
    "js"   = "application/javascript",
    "png"  = "image/png",
    "jpg"  = "image/jpeg",
    "jpeg" = "image/jpeg",
    "gif"  = "image/gif",
    "ico"  = "image/x-icon",
  }
}

# Create config.js with all necessary values
resource "local_file" "config" {
  content = templatefile("${path.module}/config.js.tpl", {
    aws_region           = var.region,
    user_pool_id         = aws_cognito_user_pool.pool.id,
    user_pool_web_client = aws_cognito_user_pool_client.client.id,
    identity_pool_id     = aws_cognito_identity_pool.main.id,
    bucket_name          = aws_s3_bucket.image_storage.bucket,
    api_gateway_url      = aws_apigatewayv2_api.image_api.api_endpoint,
    lambda_function_name = aws_lambda_function.image_processor.function_name,
    cloudfront_url       = "https://${aws_cloudfront_distribution.website.domain_name}"
  })
  filename = "${var.frontend_path}/js/config.js"

  depends_on = [
    aws_cognito_user_pool.pool,
    aws_cognito_user_pool_client.client,
    aws_cognito_identity_pool.main,
    aws_s3_bucket.image_storage,
    aws_apigatewayv2_api.image_api,
    aws_lambda_function.image_processor,
    aws_cloudfront_distribution.website
  ]
}

resource "aws_s3_object" "frontend_files" {
  for_each = toset(local.frontend_files)

  bucket       = aws_s3_bucket.frontend_hosting.id
  key          = each.value
  source       = "${var.frontend_path}/${each.value}"
  content_type = lookup(local.mime_types, element(split(".", each.value), -1), "binary/octet-stream")
  etag         = filemd5("${var.frontend_path}/${each.value}")

  depends_on = [
    aws_s3_bucket_policy.frontend_hosting
  ]
}

# Separate upload for the generated config.js file
resource "aws_s3_object" "config_js" {
  bucket       = aws_s3_bucket.frontend_hosting.id
  key          = "js/config.js"
  content      = local_file.config.content
  content_type = "application/javascript"
  etag         = local_file.config.content_md5

  depends_on = [
    aws_s3_bucket_policy.frontend_hosting,
    local_file.config
  ]
}

resource "aws_cloudfront_distribution" "website" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend_hosting.website_endpoint
    origin_id   = "S3-${var.frontend_bucket_name}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${var.frontend_bucket_name}"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  depends_on = [
    aws_s3_bucket_website_configuration.frontend_hosting,
    aws_s3_bucket_policy.frontend_hosting
  ]
}

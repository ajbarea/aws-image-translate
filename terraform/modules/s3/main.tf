# S3 module for image storage

resource "aws_s3_bucket" "images" {
  bucket = var.bucket_name
  
  tags = {
    Name    = var.bucket_name
    Purpose = "image-storage"
  }
}

# Separate resource for versioning (AWS provider v4+ requirement)
resource "aws_s3_bucket_versioning" "images" {
  count  = var.enable_versioning ? 1 : 0
  bucket = aws_s3_bucket.images.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "images" {
  bucket = aws_s3_bucket.images.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "images" {
  bucket = aws_s3_bucket.images.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle configuration to manage costs
resource "aws_s3_bucket_lifecycle_configuration" "images" {
  count  = var.enable_lifecycle ? 1 : 0
  bucket = aws_s3_bucket.images.id
  
  rule {
    id     = "transition_to_ia"
    status = "Enabled"
    
    filter {}  # Apply to all objects
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    
    expiration {
      days = 365
    }
  }
  
  rule {
    id     = "delete_incomplete_multipart_uploads"
    status = "Enabled"
    
    filter {}  # Apply to all objects
    
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

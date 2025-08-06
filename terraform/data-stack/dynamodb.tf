# terraform/dynamodb.tf

###############################################################################
# 1) User Translation History table
#    - Partition key: user_id (S)
#    - Sort key:       history_id (S)
###############################################################################
resource "aws_dynamodb_table" "translation_history" {
  name         = local.translation_history_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "user_id"
  range_key = "history_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "history_id"
    type = "S"
  }

  # Additional item attributes (no schema required):
  # - translation_id (S)
  # - image_key      (S)
  # - lang_pair      (S)
  # - timestamp      (S)

}

###############################################################################
# 2) Translations lookup table
#    - Partition key: translation_id (S)
###############################################################################
resource "aws_dynamodb_table" "translations" {
  name         = local.translations_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "translation_id"

  attribute {
    name = "translation_id"
    type = "S"
  }

  # Additional item attributes (no schema required):
  # - image_key      (S)
  # - lang_pair      (S)
  # - extracted_text (S)
  # - translated_text (S)
  # - timestamp      (S)

  global_secondary_index {
    name            = "text-language-index"
    hash_key        = "text_hash"
    range_key       = "lang_pair"
    projection_type = "ALL"
  }

  attribute {
    name = "text_hash"
    type = "S"
  }

  attribute {
    name = "lang_pair"
    type = "S"
  }

}

# EventBridge rule to trigger Reddit scraper every 5 minutes
resource "aws_cloudwatch_event_rule" "reddit_scraper_schedule" {
  name                = "${var.project_name}-reddit-scraper-schedule-${var.environment}-${local.random_suffix}"
  description         = "Trigger Reddit scraper every 5 minutes for real-time updates"
  schedule_expression = "rate(5 minutes)"
}

# EventBridge target to invoke the Reddit populator Lambda
resource "aws_cloudwatch_event_target" "reddit_scraper_target" {
  rule      = aws_cloudwatch_event_rule.reddit_scraper_schedule.name
  target_id = "RedditScraperTarget"
  arn       = aws_lambda_function.reddit_populator.arn

  input = jsonencode({
    images_per_subreddit  = 3
    subreddits            = local.reddit_subreddits
    max_images_per_lambda = 6
    real_time_mode        = true
    use_stream            = true
  })
}

# Permission for EventBridge to invoke the Lambda
resource "aws_lambda_permission" "allow_eventbridge_reddit" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.reddit_populator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reddit_scraper_schedule.arn
}

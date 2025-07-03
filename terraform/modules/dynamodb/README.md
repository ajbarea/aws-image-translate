# DynamoDB Module Architecture

```mermaid
flowchart TB
  subgraph DynamoDB Module
    direction TB
    T[aws_dynamodb_table.reddit_state]
    B[aws_dynamodb_table.reddit_state_backup]
  end
  T --> B
```

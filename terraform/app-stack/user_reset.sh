#!/bin/bash

# To find user pool id:
# $ terraform output cognito_user_pool_id

# list all users in a Cognito User Pool
# $ aws cognito-idp list-users --user-pool-id <USER_POOL_ID>

# to delete a specific user
# $ aws cognito-idp admin-delete-user --user-pool-id <USER_POOL_ID> --username <username>

# to delete all users in a Cognito User Pool
# $ aws cognito-idp list-users --user-pool-id <USER_POOL_ID>
# | jq -r '.Users[].Username' | xargs -I {} aws cognito-idp admin-delete-user --user-pool-id <USER_POOL_ID> --username {}

echo "Fetching Cognito User Pool ID from Terraform..."
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)

if [ -z "$USER_POOL_ID" ]; then
    echo "❌ Error: Could not fetch User Pool ID from Terraform."
    echo "Make sure you're in the terraform directory and have run 'terraform apply'."
    exit 1
fi

echo "Found User Pool ID: $USER_POOL_ID"

echo "Fetching all users from Cognito User Pool: $USER_POOL_ID"

# Get all usernames
USERNAMES=$(aws cognito-idp list-users --user-pool-id $USER_POOL_ID --query 'Users[].Username' --output text)

if [ -z "$USERNAMES" ]; then
    echo "No users found in the User Pool."
    exit 0
fi

echo "Found users: $USERNAMES"

# Confirm deletion
read -p "Are you sure you want to delete all users in the User Pool? This action cannot be undone. (Y/n): " confirm
if [[ "$confirm" != "Y" ]]; then
    echo "Aborting user deletion."
    exit 0
fi

echo "Deleting all users..."

# Delete each user
for username in $USERNAMES; do
    echo "Deleting user: $username"
    aws cognito-idp admin-delete-user --user-pool-id $USER_POOL_ID --username "$username"
    if [ $? -eq 0 ]; then
        echo "✅ Successfully deleted: $username"
    else
        echo "❌ Failed to delete: $username"
    fi
done

echo "Done!"

#!/usr/bin/env python3
"""
AWS Image Translate - Cognito Setup Script
Creates minimal Cognito resources for local development
"""

import json
import subprocess
import sys


def run_cmd(cmd: str) -> str:
    """Run command and return output"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def main() -> None:
    print("🚀 Creating minimal Cognito setup...")

    # Step 1: Create User Pool
    print("📝 Creating User Pool...")
    cmd1 = 'aws cognito-idp create-user-pool --pool-name "aws-image-translate-dev-pool" --region us-east-1'
    output1 = run_cmd(cmd1)
    user_pool_data = json.loads(output1)
    user_pool_id = user_pool_data["UserPool"]["Id"]
    print(f"✅ User Pool: {user_pool_id}")

    # Step 2: Create User Pool Client
    print("📱 Creating User Pool Client...")
    cmd2 = f'aws cognito-idp create-user-pool-client --user-pool-id {user_pool_id} --client-name "dev-client" --no-generate-secret --region us-east-1'
    output2 = run_cmd(cmd2)
    client_data = json.loads(output2)
    client_id = client_data["UserPoolClient"]["ClientId"]
    print(f"✅ Client: {client_id}")

    # Step 3: Create Identity Pool
    print("🆔 Creating Identity Pool...")
    provider_name = f"cognito-idp.us-east-1.amazonaws.com/{user_pool_id}"
    cmd3 = f'aws cognito-identity create-identity-pool --identity-pool-name "dev-identity-pool" --no-allow-unauthenticated-identities --cognito-identity-providers ProviderName={provider_name},ClientId={client_id} --region us-east-1'
    output3 = run_cmd(cmd3)
    identity_data = json.loads(output3)
    identity_pool_id = identity_data["IdentityPoolId"]
    print(f"✅ Identity Pool: {identity_pool_id}")

    print("\n🎉 Setup complete! Add to .env.local:")
    print("COGNITO_REGION=us-east-1")
    print(f"COGNITO_USER_POOL_ID={user_pool_id}")
    print(f"COGNITO_APP_CLIENT_ID={client_id}")
    print(f"COGNITO_IDENTITY_POOL_ID={identity_pool_id}")

    print("\n📝 Frontend config.js:")
    print("const AWS_CONFIG = {")
    print('  region: "us-east-1",')
    print(f'  userPoolId: "{user_pool_id}",')
    print(f'  userPoolWebClientId: "{client_id}",')
    print(f'  identityPoolId: "{identity_pool_id}",')
    print('  bucketName: "ajbarea-aws-translate",')
    print('  apiGatewayUrl: "http://localhost:8000"')
    print("};")


if __name__ == "__main__":
    main()

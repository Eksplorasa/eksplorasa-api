#!/bin/bash

# Deploy script for Eksplorasa API CDK stack
set -e  # Exit on any error

# Configuration
AWS_ACCOUNT_ID="315565838153"
AWS_REGION="ap-southeast-3"  
STAGE="dev"  # Set the stage for this deployment
STACK_NAME="EksplorasaApiStack-${STAGE}"

echo "🚀 Starting deployment of Eksplorasa API to AWS account: $AWS_ACCOUNT_ID"
echo "📍 Region: $AWS_REGION"
echo "📦 Stack: $STACK_NAME"
echo ""

# Check if AWS CLI is configured
echo "🔐 Checking AWS credentials..."
aws sts get-caller-identity --profile eksplorasa-dev > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ AWS credentials not configured for 'eksplorasa-dev' profile. Please run 'aws configure --profile eksplorasa-dev' first."
    exit 1
fi

# Verify we're targeting the correct account
CURRENT_ACCOUNT=$(aws sts get-caller-identity --profile eksplorasa-dev --query Account --output text)
if [ "$CURRENT_ACCOUNT" != "$AWS_ACCOUNT_ID" ]; then
    echo "⚠️  Warning: Current AWS account ($CURRENT_ACCOUNT) doesn't match target account ($AWS_ACCOUNT_ID)"
    echo "Please switch to the correct AWS profile or account."
    exit 1
fi

echo "✅ AWS credentials verified for account: $CURRENT_ACCOUNT"
echo ""

# Install dependencies
echo "📦 Installing Node.js dependencies..."
npm ci

# Build the project
echo "� Building the project..."
npm run build

# Deploy the stack
echo "� Deploying CDK stack..."
export STAGE=$STAGE
npx cdk deploy --require-approval never --region $AWS_REGION --context stage=$STAGE --profile eksplorasa-dev

echo ""
echo "✅ Deployment completed successfully!"

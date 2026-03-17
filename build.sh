#!/bin/bash
set -e

STACK_NAME="mp-saas-tester"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
FUNCTION_NAME="mp-saas-tester"

echo "==> Packaging Lambda..."
cd backend
pip3 install -r requirements.txt -t package/ -q
cp handler.py package/
cd package && zip -r ../function.zip . -q && cd ..
rm -rf package
cd ..

echo "==> Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name $STACK_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION

echo "==> Updating Lambda code..."
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://backend/function.zip \
  --region $REGION \
  --query "FunctionArn" --output text

echo "==> Getting stack outputs..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucket'].OutputValue" \
  --output text)

TOOL_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME --region $REGION \
  --query "Stacks[0].Outputs[?OutputKey=='TestToolUrl'].OutputValue" \
  --output text)

echo "==> Uploading frontend with API endpoint injected..."
sed "s|__API_ENDPOINT__|$API_ENDPOINT|g" frontend/index.html > /tmp/index.html
aws s3 cp /tmp/index.html s3://$FRONTEND_BUCKET/index.html \
  --content-type text/html --region $REGION

echo ""
echo "========================================"
echo "  SaaS Integration Tester is live!"
echo ""
echo "  Open this URL in your browser:"
echo "  $TOOL_URL"
echo "========================================"

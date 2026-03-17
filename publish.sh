#!/bin/bash
set -e

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ASSETS_BUCKET="${MP_ASSETS_BUCKET:-}"

if [ -z "$ASSETS_BUCKET" ]; then
  echo "ERROR: Set MP_ASSETS_BUCKET env var to your team's S3 bucket name"
  echo "  export MP_ASSETS_BUCKET=your-bucket-name"
  exit 1
fi

TEMPLATE_S3_URL="https://$ASSETS_BUCKET.s3.$REGION.amazonaws.com/mp-saas-tester/template.yaml"
LAUNCH_URL="https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?templateURL=$TEMPLATE_S3_URL&stackName=mp-saas-tester"

echo "==> Uploading CloudFormation template..."
aws s3 cp infra/template.yaml s3://$ASSETS_BUCKET/mp-saas-tester/template.yaml \
  --region $REGION

echo "==> Uploading Lambda zip..."
cd backend
pip3 install -r requirements.txt -t package/ -q
cp handler.py package/
cd package && zip -r ../function.zip . -q && cd ..
rm -rf package
cd ..
aws s3 cp backend/function.zip s3://$ASSETS_BUCKET/mp-saas-tester/function.zip \
  --region $REGION

echo "==> Uploading frontend..."
aws s3 cp frontend/index.html s3://$ASSETS_BUCKET/mp-saas-tester/index.html \
  --content-type text/html --region $REGION

echo "==> Updating Launch Stack URL in workshop content..."
sed -i '' "s|TEMPLATE_S3_URL|$TEMPLATE_S3_URL|g" workshop/content/en-US/index.md

echo ""
echo "========================================"
echo "  Assets published to S3"
echo ""
echo "  Launch Stack URL:"
echo "  $LAUNCH_URL"
echo ""
echo "  Add this button to the workshop lab:"
echo "  [![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]($LAUNCH_URL)"
echo "========================================"

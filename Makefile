.PHONY: build deploy clean

build:
	cp frontend/index.html backend/index.html
	sam build --template-file infra/template.yaml

deploy: build
	sam deploy

clean:
	sam delete --stack-name aws-marketplace-seller-toolkit --region us-east-1

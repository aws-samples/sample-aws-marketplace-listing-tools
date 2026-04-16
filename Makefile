.PHONY: build deploy clean

STACK_NAME ?= aws-marketplace-seller-toolkit-$(shell date +%Y%m%d%H%M%S)

build:
	cp frontend/index.html backend/index.html
	sam build --template-file infra/template.yaml

deploy: build
	@echo "Deploying stack: $(STACK_NAME)"
	sam deploy --stack-name $(STACK_NAME)
	@echo ""
	@echo "Stack name: $(STACK_NAME)"
	@echo "To delete: make clean STACK_NAME=$(STACK_NAME)"

clean:
	sam delete --stack-name $(STACK_NAME) --region us-east-1 --no-prompts

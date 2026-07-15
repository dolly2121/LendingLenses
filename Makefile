.PHONY: data pipeline dashboard service demo test

data:
	python pipeline/generate_data.py

pipeline:
	python -m pipeline.run_pipeline

dashboard:
	streamlit run dashboard/app.py

service:
	uvicorn ai_service.main:app --reload

demo:
	pip install -r requirements.txt
	python -m pipeline.demo

test:
	pytest

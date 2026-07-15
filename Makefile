.PHONY: data pipeline dashboard service demo test

data:
	python pipeline/generate_data.py

pipeline:
	python pipeline/run_pipeline.py

dashboard:
	streamlit run dashboard/app.py

service:
	uvicorn ai_service.main:app --reload

demo:
	python pipeline/run_pipeline.py

test:
	pytest

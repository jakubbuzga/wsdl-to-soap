# backend/app/main.py
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from .models import GenerationResponse
from .graph_logic import graph_app, GraphState

app = FastAPI(title="WSDL Test Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/generations", response_model=GenerationResponse)
async def create_generation(
    wsdl_file: UploadFile = File(...),
    test_options: List[str] = Form(...)
):
    """
    Starts a new test generation graph.
    Accepts a WSDL file and test options, returns the generated SoapUI project.
    """
    generation_id = str(uuid.uuid4())
    wsdl_content = (await wsdl_file.read()).decode("utf-8")

    initial_state = {
        "wsdl_content": wsdl_content,
        "file_name": wsdl_file.filename or "service.wsdl",
        "test_options": test_options,
    }

    final_state = None
    try:
        # Stream through the graph to execute it
        for state_update in graph_app.stream(initial_state):
            final_state = state_update

        # The final state is the last message from the stream
        if not final_state:
            raise HTTPException(status_code=500, detail="Graph execution failed to produce a result.")

        final_values = list(final_state.values())[0]

        if error_message := final_values.get("error_message"):
            # We include the generationId in the error response for potential debugging
            return GenerationResponse(generationId=generation_id, errorMessage=error_message)

        return GenerationResponse(
            generationId=generation_id,
            xmlContent=final_values.get("soapui_project_xml"),
        )
    except Exception as e:
        # Catch any other exceptions during graph execution
        return GenerationResponse(
            generationId=generation_id,
            errorMessage=f"An unexpected error occurred: {e}"
        )

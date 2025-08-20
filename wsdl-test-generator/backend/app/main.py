# backend/app/main.py
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict

from .models import GenerationResponse, FeedbackRequest, FeedbackResponse
from .graph_logic import graph_app, GraphState

app = FastAPI(title="WSDL Test Generator API")

# In-memory storage for graph states. In production, use Redis or a database.
graph_sessions: Dict[str, List] = {}

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
    Accepts a WSDL file and test options, returns an initial result and a generation ID.
    """
    generation_id = str(uuid.uuid4())
    wsdl_content = (await wsdl_file.read()).decode("utf-8")

    initial_state: GraphState = {
        "wsdl_content": wsdl_content,
        "test_options": test_options,
        "feedback_history": [],
        "generated_xml": "",
        "error_message": "",
        "attempt_count": 0,
    }

    config = {"configurable": {"thread_id": generation_id}}

    try:
        # The stream method will now run the graph until it's interrupted
        for _ in graph_app.stream(initial_state, config=config):
            pass

        final_state = graph_app.get_state(config)

        if final_state is None:
            raise HTTPException(status_code=500, detail="Graph execution failed to produce a state.")

        return GenerationResponse(
            generationId=generation_id,
            xmlContent=final_state.values.get("generated_xml"),
            errorMessage=final_state.values.get("error_message")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during graph execution: {e}")


@app.post("/api/generations/{generation_id}/feedback", response_model=FeedbackResponse)
async def regenerate_with_feedback(
    generation_id: str,
    request: FeedbackRequest
):
    """
    Starts a new graph execution with the provided feedback.
    """
    config = {"configurable": {"thread_id": generation_id}}

    # Retrieve the last state of the graph to get original context
    current_state = graph_app.get_state(config)

    if current_state is None:
        raise HTTPException(status_code=404, detail="Generation ID not found.")

    # Start a new run with the updated feedback history
    new_initial_state = {
        "wsdl_content": current_state.values["wsdl_content"],
        "test_options": current_state.values["test_options"],
        "feedback_history": current_state.values["feedback_history"] + [request.feedback],
        "generated_xml": "",
        "error_message": "",
        "attempt_count": 0,
    }

    try:
        # Run the graph from the beginning with the new feedback
        for _ in graph_app.stream(new_initial_state, config=config):
            pass

        final_state = graph_app.get_state(config)

        if final_state is None:
            raise HTTPException(status_code=500, detail="Graph execution failed to produce a state.")

        return FeedbackResponse(
            xmlContent=final_state.values.get("generated_xml"),
            errorMessage=final_state.values.get("error_message")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred during graph resumption: {e}")

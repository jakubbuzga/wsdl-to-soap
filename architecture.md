# Implementation Plan: WSDL-to-SOAP Test Generator

**Objective:** Develop a full-stack application that accepts a WSDL file, uses an LLM via a stateful LangGraph agent to generate SOAP test cases, and allows users to provide feedback for regeneration.

**Technology Stack:**
* **Frontend:** React (with TypeScript, Vite, Material-UI)
* **Backend:** Python with FastAPI
* **LLM Orchestration:** LangGraph
* **LLM (Local):** Ollama
* **Infrastructure:** Docker & Docker Compose

---

## Phase 1: Project Setup & Core LLM Logic

**Goal:** Establish the project structure and implement the core, stateful test generation logic using LangGraph.

### Task 1.1: Initialize Project Monorepo Structure

* **Objective:** Create a clean directory structure to house the frontend and backend code separately.
* **Instructions for AI Agent:**
    1.  Execute the following commands in your terminal:
        ```bash
        mkdir -p wsdl-test-generator/backend/app
        mkdir wsdl-test-generator/frontend
        touch wsdl-test-generator/README.md
        touch wsdl-test-generator/backend/app/__init__.py
        ```
* **Acceptance Criteria:**
    * The file structure `wsdl-test-generator/backend/app/` and `wsdl-test-generator/frontend/` exists.

### Task 1.2: Set up the Python Backend Environment

* **Objective:** Initialize the FastAPI project with all necessary dependencies.
* **Instructions for AI Agent:**
    1.  Navigate to the `wsdl-test-generator/backend` directory.
    2.  Create and activate a Python virtual environment:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    3.  Create a `requirements.txt` file with the following content:
        ```
        fastapi
        uvicorn[standard]
        pydantic
        python-multipart
        langchain
        langgraph
        langchain_community
        langchain_core
        ollama
        zeep
        ```
    4.  Install the dependencies: `pip install -r requirements.txt`.
    5.  Create the initial application file at `backend/app/main.py`:
        ```python
        # backend/app/main.py
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI(title="WSDL Test Generator API")

        # Configure CORS for frontend access
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://localhost"], # Add frontend dev and production origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/api/health")
        def health_check():
            """Health check endpoint to ensure the server is running."""
            return {"status": "ok"}
        ```
* **Acceptance Criteria:**
    * Dependencies are installed in the `venv`.
    * Running `uvicorn app.main:app --reload --host 0.0.0.0` from the `backend` directory starts the server.
    * Accessing `http://127.0.0.1:8000/api/health` returns `{"status": "ok"}`.

### Task 1.3: Set up the React Frontend Environment

* **Objective:** Initialize a modern React project using Vite and TypeScript.
* **Instructions for AI Agent:**
    1.  Navigate to the project's root directory (`wsdl-test-generator`).
    2.  Execute the Vite scaffolding command:
        ```bash
        npm create vite@latest frontend -- --template react-ts
        ```
    3.  Navigate into the new `frontend` directory: `cd frontend`.
    4.  Install all required dependencies:
        ```bash
        npm install axios react-syntax-highlighter @mui/material @emotion/react @emotion/styled @mui/icons-material
        npm install -D @types/react-syntax-highlighter
        ```
    5.  Clean up the default template: delete `src/App.css` and `src/assets/react.svg`. Replace the content of `src/App.tsx` with a basic placeholder.
* **Acceptance Criteria:**
    * The `frontend` directory contains a functional React + TypeScript project.
    * `npm run dev` starts the development server successfully.

### Task 1.4: Implement the Core LangGraph Logic

* **Objective:** Create the stateful graph that will manage the test generation and feedback loop.
* **Instructions for AI Agent:**
    1.  Create a new file at `backend/app/graph_logic.py`.
    2.  Populate the file with the following code. This code defines the state, nodes, and the graph itself.

        ```python
        # backend/app/graph_logic.py
        import os
        from typing import TypedDict, List
        from langchain_core.prompts import PromptTemplate
        from langchain_community.llms.ollama import Ollama
        from langgraph.graph import StateGraph, END, Interrupt

        # Ensure the Ollama service is accessible. Update if your service runs elsewhere.
        OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        LLM_MODEL = os.getenv("LLM_MODEL", "llama3")

        class GraphState(TypedDict):
            """Represents the state of our graph."""
            wsdl_content: str
            test_options: List[str]
            prompt: str
            generated_xml: str
            feedback_history: List[str]
            error_message: str
            attempt_count: int

        # --- Node Functions ---

        def generate_initial_prompt(state: GraphState) -> GraphState:
            """Generates the initial prompt for the LLM based on WSDL and user options."""
            print("--- Generating Initial Prompt ---")
            template = """
            You are a world-class expert in SOAP API testing. Your task is to generate a comprehensive set of SOAP XML test cases based on the provided WSDL file.

            The user has requested the following types of tests: {test_options}

            Please adhere to these rules:
            1. The output MUST be a single, valid XML document.
            2. The XML document should contain one or more `<soap:Envelope>` elements.
            3. Each envelope should represent a complete test case for an operation defined in the WSDL.
            4. Populate the XML body with realistic and relevant sample data. For negative or edge cases, use data that tests those specific conditions (e.g., invalid formats, empty fields, oversized values).
            5. Do NOT include any explanations, markdown formatting, or text outside of the final XML document.

            WSDL Content:
            ```xml
            {wsdl_content}
            ```
            """
            prompt = PromptTemplate(
                template=template,
                input_variables=["test_options", "wsdl_content"],
            ).format(
                test_options=", ".join(state["test_options"]),
                wsdl_content=state["wsdl_content"],
            )
            return {"prompt": prompt, "attempt_count": 1}

        def generate_with_feedback_prompt(state: GraphState) -> GraphState:
            """Refines the prompt based on user feedback."""
            print("--- Generating Prompt with Feedback ---")
            template = """
            You are a world-class expert in SOAP API testing. A previous attempt to generate SOAP tests was incorrect. Please try again, carefully considering the user's feedback.

            User Feedback:
            "{feedback}"

            Original Request Details:
            - Test Types: {test_options}
            - Original WSDL:
            ```xml
            {wsdl_content}
            ```

            Please regenerate the tests, addressing the feedback provided. The output must be a single, valid XML document containing only the SOAP envelopes, with no extra text or explanations.
            """
            last_feedback = state["feedback_history"][-1]
            prompt = PromptTemplate(
                template=template,
                input_variables=["feedback", "test_options", "wsdl_content"],
            ).format(
                feedback=last_feedback,
                test_options=", ".join(state["test_options"]),
                wsdl_content=state["wsdl_content"],
            )
            return {"prompt": prompt, "attempt_count": state["attempt_count"] + 1}

        def call_llm(state: GraphState) -> GraphState:
            """Calls the LLM with the current prompt and updates the state."""
            print(f"--- Calling LLM (Attempt {state['attempt_count']}) ---")
            try:
                llm = Ollama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.1)
                response = llm.invoke(state["prompt"])
                return {"generated_xml": response, "error_message": None}
            except Exception as e:
                print(f"Error calling LLM: {e}")
                return {"generated_xml": None, "error_message": str(e)}

        # --- Conditional Edge Logic ---

        def decide_entry_point(state: GraphState) -> str:
            """Determines whether to start with an initial prompt or a feedback-based one."""
            print("--- Deciding Entry Point ---")
            if not state.get("feedback_history"):
                return "generate_initial_prompt"
            else:
                return "generate_with_feedback_prompt"

        # --- Assemble the Graph ---

        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("generate_initial_prompt", generate_initial_prompt)
        workflow.add_node("generate_with_feedback_prompt", generate_with_feedback_prompt)
        workflow.add_node("call_llm", call_llm)

        # Set entry point
        workflow.set_conditional_entry_point(
            decide_entry_point,
            {
                "generate_initial_prompt": "generate_initial_prompt",
                "generate_with_feedback_prompt": "generate_with_feedback_prompt",
            },
        )

        # Add edges
        workflow.add_edge("generate_initial_prompt", "call_llm")
        workflow.add_edge("generate_with_feedback_prompt", "call_llm")

        # After the LLM call, the graph should interrupt to wait for feedback
        workflow.add_node("pause_for_feedback", Interrupt())
        workflow.add_edge("call_llm", "pause_for_feedback")

        # Compile the graph
        graph_app = workflow.compile()
        ```
* **Acceptance Criteria:**
    * The `backend/app/graph_logic.py` file contains a compiled LangGraph `app`.
    * The code is free of syntax errors.

### Task 1.5: Test the LangGraph Logic in Isolation

* **Objective:** Verify that the graph works as expected before connecting it to the API.
* **Instructions for AI Agent:**
    1.  Create a new file at `backend/app/test_graph.py`.
    2.  Populate it with a script that runs a sample WSDL through the graph, simulates feedback, and resumes the graph.
        ```python
        # backend/app/test_graph.py
        from app.graph_logic import graph_app, GraphState

        # A sample WSDL for testing purposes
        sample_wsdl = """
        <definitions xmlns="[http://schemas.xmlsoap.org/wsdl/](http://schemas.xmlsoap.org/wsdl/)"
             xmlns:soap="[http://schemas.xmlsoap.org/wsdl/soap/](http://schemas.xmlsoap.org/wsdl/soap/)"
             xmlns:tns="[http://www.example.com/calculator](http://www.example.com/calculator)"
             xmlns:xsd="[http://www.w3.org/2001/XMLSchema](http://www.w3.org/2001/XMLSchema)"
             name="CalculatorService"
             targetNamespace="[http://www.example.com/calculator](http://www.example.com/calculator)">
            <message name="AddRequest">
                <part name="a" type="xsd:int"/>
                <part name="b" type="xsd:int"/>
            </message>
            <message name="AddResponse">
                <part name="result" type="xsd:int"/>
            </message>
            <portType name="CalculatorPortType">
                <operation name="add">
                    <input message="tns:AddRequest"/>
                    <output message="tns:AddResponse"/>
                </operation>
            </portType>
            <binding name="CalculatorBinding" type="tns:CalculatorPortType">
                <soap:binding style="rpc" transport="[http://schemas.xmlsoap.org/soap/http](http://schemas.xmlsoap.org/soap/http)"/>
                <operation name="add">
                    <soap:operation soapAction="add"/>
                    <input><soap:body use="literal" namespace="[http://www.example.com/calculator](http://www.example.com/calculator)"/></input>
                    <output><soap:body use="literal" namespace="[http://www.example.com/calculator](http://www.example.com/calculator)"/></output>
                </operation>
            </binding>
            <service name="CalculatorService">
                <port name="CalculatorPort" binding="tns:CalculatorBinding">
                    <soap:address location="[http://www.example.com/calculator](http://www.example.com/calculator)"/>
                </port>
            </service>
        </definitions>
        """

        # --- Test Execution ---
        if __name__ == "__main__":
            print("--- Starting Graph Test ---")

            initial_state: GraphState = {
                "wsdl_content": sample_wsdl,
                "test_options": ["happy_path", "negative case with zero"],
                "feedback_history": [],
            }

            # 1. Initial run
            print("\n--- [Step 1] Initial Generation ---")
            final_state = None
            for state_update in graph_app.stream(initial_state):
                final_state = list(state_update.values())[0]
                print(f"Node '{list(state_update.keys())[0]}' finished. Current state keys: {final_state.keys()}")
            
            print("\n--- [Step 1] Result ---")
            print("Generated XML:", final_state.get("generated_xml"))

            # 2. Simulate feedback and resume
            print("\n--- [Step 2] Providing Feedback and Resuming ---")
            user_feedback = "The negative test is missing. Please add a test where 'a' is zero."
            final_state["feedback_history"].append(user_feedback)
            
            resumed_final_state = None
            for state_update in graph_app.stream(final_state):
                resumed_final_state = list(state_update.values())[0]
                print(f"Node '{list(state_update.keys())[0]}' finished. Current state keys: {resumed_final_state.keys()}")

            print("\n--- [Step 2] Result after Feedback ---")
            print("Regenerated XML:", resumed_final_state.get("generated_xml"))
            print(f"Total attempts: {resumed_final_state.get('attempt_count')}")

            print("\n--- Graph Test Finished ---")

        ```
    3.  Run the test from the `backend` directory (ensure Ollama is running): `python -m app.test_graph`.
* **Acceptance Criteria:**
    * The script runs without errors.
    * The output shows the graph progressing through the nodes for both the initial run and the feedback run.
    * XML content is printed to the console for both steps.

---

## Phase 2: Backend API Development

**Goal:** Expose the LangGraph functionality through a robust FastAPI server.

### Task 2.1: Define API Data Models

* **Objective:** Create Pydantic models to validate API request and response bodies.
* **Instructions for AI Agent:**
    1.  Create a new file at `backend/app/models.py`.
    2.  Populate it with the following code:
        ```python
        # backend/app/models.py
        from pydantic import BaseModel
        from typing import List, Optional

        class GenerationResponse(BaseModel):
            generationId: str
            xmlContent: Optional[str] = None
            errorMessage: Optional[str] = None

        class FeedbackRequest(BaseModel):
            feedback: str

        class FeedbackResponse(BaseModel):
            xmlContent: Optional[str] = None
            errorMessage: Optional[str] = None
        ```
* **Acceptance Criteria:**
    * The `backend/app/models.py` file is created and contains the specified Pydantic models.

### Task 2.2: Implement API Endpoints in FastAPI

* **Objective:** Create the HTTP endpoints for the frontend to interact with.
* **Instructions for AI Agent:**
    1.  Replace the content of `backend/app/main.py` with the following complete code:
        ```python
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
            }

            final_state = None
            try:
                for state_update in graph_app.stream(initial_state):
                    final_state = list(state_update.values())[0]
                
                if final_state is None:
                    raise HTTPException(status_code=500, detail="Graph execution failed to produce a state.")

                # Save the final snapshot of the graph state to resume later
                graph_sessions[generation_id] = final_state
                
                return GenerationResponse(
                    generationId=generation_id,
                    xmlContent=final_state.get("generated_xml"),
                    errorMessage=final_state.get("error_message")
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"An error occurred during graph execution: {e}")


        @app.post("/api/generations/{generation_id}/feedback", response_model=FeedbackResponse)
        async def regenerate_with_feedback(
            generation_id: str,
            request: FeedbackRequest
        ):
            """
            Resumes a graph execution with new user feedback.
            """
            if generation_id not in graph_sessions:
                raise HTTPException(status_code=404, detail="Generation ID not found.")

            # Retrieve the last state of the graph
            current_state = graph_sessions[generation_id]
            
            # Add new feedback to the history
            current_state["feedback_history"].append(request.feedback)
            
            final_state = None
            try:
                # Resume the graph from where it was interrupted
                for state_update in graph_app.stream(current_state):
                    final_state = list(state_update.values())[0]
                
                if final_state is None:
                    raise HTTPException(status_code=500, detail="Graph execution failed to produce a state.")

                # Update the session with the new final state
                graph_sessions[generation_id] = final_state

                return FeedbackResponse(
                    xmlContent=final_state.get("generated_xml"),
                    errorMessage=final_state.get("error_message")
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"An error occurred during graph resumption: {e}")

        ```
* **Acceptance Criteria:**
    * The API server runs without errors.
    * The `/docs` page shows the two new POST endpoints.
    * The endpoints can be tested and return the expected responses.

---

## Phase 3: Frontend Development & API Integration

**Goal:** Build the user interface and connect it to the backend API.

### Task 3.1: Implement API Client Service

* **Objective:** Create a centralized place for making API calls.
* **Instructions for AI Agent:**
    1.  Create `frontend/src/services/api.ts` and populate it:
        ```typescript
        // frontend/src/services/api.ts
        import axios from 'axios';

        const apiClient = axios.create({
          baseURL: 'http://localhost:8000/api', // Adjust if backend URL is different
          headers: {
            'Content-Type': 'application/json',
          },
        });

        // --- TypeScript Interfaces ---
        export interface GenerationResponse {
          generationId: string;
          xmlContent?: string;
          errorMessage?: string;
        }

        export interface FeedbackResponse {
          xmlContent?: string;
          errorMessage?: string;
        }

        // --- API Functions ---
        export const generateTests = async (
          wsdlFile: File,
          testOptions: string[]
        ): Promise<GenerationResponse> => {
          const formData = new FormData();
          formData.append('wsdl_file', wsdlFile);
          testOptions.forEach(option => formData.append('test_options', option));

          const response = await apiClient.post<GenerationResponse>('/generations', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          });
          return response.data;
        };

        export const submitFeedback = async (
          generationId: string,
          feedback: string
        ): Promise<FeedbackResponse> => {
          const response = await apiClient.post<FeedbackResponse>(
            `/generations/${generationId}/feedback`,
            { feedback }
          );
          return response.data;
        };
        ```
* **Acceptance Criteria:**
    * The `api.ts` service file is implemented with strongly-typed functions.

### Task 3.2: Build the UI and Connect State Logic

* **Objective:** Implement the full functionality of the UI, including state management and API calls.
* **Instructions for AI Agent:**
    1.  This is a larger task. Implement the logic in `frontend/src/App.tsx`.
    2.  Use `useState` hooks to manage `isLoading`, `xmlContent`, `generationId`, `errorMessage`, `selectedFile`, `testOptions`, and `feedbackText`.
    3.  Create handler functions for form submission (`handleGenerate`) and feedback submission (`handleFeedback`).
    4.  These handlers should call the functions from your `api.ts` service, update the state with the results (e.g., `setXmlContent`, `setIsLoading`), and handle any errors.
    5.  Structure the `App.tsx` return JSX to conditionally render components:
        * Show a loading spinner (`CircularProgress` from MUI) when `isLoading` is true.
        * Show an error message (`Alert` from MUI) when `errorMessage` is set.
        * Show the main form for uploading the WSDL and selecting options.
        * After a successful generation, show the results display and the feedback form.
    6.  Use `react-syntax-highlighter` to display the `xmlContent` with appropriate styling.
    7.  Implement a simple download button that creates a blob from `xmlContent` and triggers a browser download.
* **Acceptance Criteria:**
    * The application is fully interactive.
    * The user can upload a file, select options, and generate tests.
    * The results are displayed with syntax highlighting.
    * The user can submit feedback to regenerate the tests, and the display updates accordingly.
    * Loading and error states are handled gracefully.

---

## Phase 4: Containerization & Finalization

**Goal:** Package the entire application for easy deployment using Docker.

### Task 4.1: Create Dockerfile for the Backend

* **Objective:** Create a Docker image for the FastAPI application.
* **Instructions for AI Agent:**
    1.  Create a file at `backend/Dockerfile`:
        ```dockerfile
        # backend/Dockerfile
        # Use an official Python runtime as a parent image
        FROM python:3.11-slim

        # Set the working directory in the container
        WORKDIR /code

        # Copy the dependencies file to the working directory
        COPY ./requirements.txt .

        # Install any needed packages specified in requirements.txt
        RUN pip install --no-cache-dir --upgrade -r requirements.txt

        # Copy the rest of the application's code
        COPY ./app /code/app

        # Expose the port the app runs on
        EXPOSE 8000

        # Command to run the application
        CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
        ```
* **Acceptance Criteria:**
    * `docker build -t wsdl-backend .` completes successfully from the `backend` directory.

### Task 4.2: Create Dockerfile for the Frontend (Nginx)

* **Objective:** Create a production-ready Docker image for the React app served by Nginx.
* **Instructions for AI Agent:**
    1.  First, create `frontend/nginx.conf`:
        ```nginx
        # frontend/nginx.conf
        server {
            listen 80;
            server_name localhost;

            root /usr/share/nginx/html;
            index index.html;

            location / {
                try_files $uri /index.html;
            }

            location /api {
                proxy_pass http://backend:8000; # Proxy requests to the backend service
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
        }
        ```
    2.  Next, create `frontend/Dockerfile`:
        ```dockerfile
        # frontend/Dockerfile
        # Stage 1: Build the React application
        FROM node:20-alpine AS builder

        WORKDIR /app

        COPY package*.json ./
        RUN npm install
        COPY . .
        RUN npm run build

        # Stage 2: Serve the application with Nginx
        FROM nginx:stable-alpine

        # Copy the built assets from the builder stage
        COPY --from=builder /app/dist /usr/share/nginx/html

        # Copy the Nginx configuration
        COPY nginx.conf /etc/nginx/conf.d/default.conf

        # Expose port 80
        EXPOSE 80

        # Start Nginx
        CMD ["nginx", "-g", "daemon off;"]
        ```
* **Acceptance Criteria:**
    * `docker build -t wsdl-frontend .` completes successfully from the `frontend` directory.

### Task 4.3: Create Docker Compose Configuration

* **Objective:** Define and orchestrate all application services to run together.
* **Instructions for AI Agent:**
    1.  In the project root (`wsdl-test-generator`), create `docker-compose.yml`:
        ```yaml
        # docker-compose.yml
        version: '3.8'

        services:
          frontend:
            build:
              context: ./frontend
            container_name: wsdl_frontend
            ports:
              - "80:80" # Map host port 80 to container port 80
            depends_on:
              - backend
            networks:
              - wsdl_network

          backend:
            build:
              context: ./backend
            container_name: wsdl_backend
            ports:
              - "8000:8000" # Expose for direct API access if needed
            environment:
              - OLLAMA_BASE_URL=http://ollama:11434
              - LLM_MODEL=llama3 # Or any other model you have pulled
            depends_on:
              - ollama
            networks:
              - wsdl_network

          ollama:
            image: ollama/ollama:latest
            container_name: ollama_service
            ports:
              - "11434:11434"
            volumes:
              - ollama_data:/root/.ollama
            networks:
              - wsdl_network

        volumes:
          ollama_data:

        networks:
          wsdl_network:
            driver: bridge
        ```
* **Acceptance Criteria:**
    * Running `docker-compose up --build` from the root directory starts all three containers.
    * The application is fully accessible at `http://localhost`.
    * The entire workflow from file upload to feedback submission functions correctly.

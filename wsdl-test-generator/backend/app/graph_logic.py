# backend/app/graph_logic.py
import os
import re
from typing import TypedDict, List
from langchain_core.prompts import PromptTemplate
from langchain_community.llms.ollama import Ollama
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Ensure the Ollama service is accessible. Update if your service runs elsewhere.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
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
    You are a world-class expert in SoapUI test automation. Your task is to generate a complete, importable SoapUI project as a single XML file based on the provided WSDL.

    The user has requested the following types of test suites: {test_options}.

    Please adhere to these rules:
    1. The output MUST be a single, valid XML document that represents a SoapUI project.
    2. The project should be named "Generated-SoapUI-Project".
    3. For each operation in the WSDL, create a corresponding test case.
    4. For each test case, include at least one relevant assertion. For happy path tests, add a "Valid HTTP Status Codes" assertion for status 200. For negative or edge case tests, consider adding "Contains" or "XPath Match" assertions to check for specific fault strings or error messages in the response.
    5. Populate the request body in each test step with realistic and relevant sample data based on the test type.
    6. Do NOT include any explanations, markdown formatting, or any other text outside of the final XML document. The output should be ready to be saved as a `.xml` file and imported directly into SoapUI.

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
    You are a world-class expert in SoapUI test automation. A previous attempt to generate a SoapUI project was incorrect. Please try again, carefully considering the user's feedback.

    User Feedback:
    "{feedback}"

    Original Request Details:
    - Test Suites: {test_options}
    - Original WSDL:
    ```xml
    {wsdl_content}
    ```

    Please regenerate the SoapUI project, addressing the feedback provided. The output must be a single, valid XML document representing a complete SoapUI project with test suites, test cases, and assertions, ready for direct import. Do not include any text or explanations outside of the XML document.
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

def pause_for_feedback(state: GraphState) -> GraphState:
    """A node that does nothing, used as a static breakpoint for human-in-the-loop."""
    print("--- Pausing for feedback ---")
    return state

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
workflow.add_node("pause_for_feedback", pause_for_feedback)

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
workflow.add_edge("call_llm", "pause_for_feedback")
workflow.add_edge("pause_for_feedback", END)


# Compile the graph
checkpointer = MemorySaver()
graph_app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["pause_for_feedback"]
)

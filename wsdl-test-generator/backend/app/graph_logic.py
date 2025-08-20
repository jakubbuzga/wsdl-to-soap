# backend/app/graph_logic.py
import os
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

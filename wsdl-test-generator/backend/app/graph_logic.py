# backend/app/graph_logic.py
import os
import json
from typing import TypedDict, List, Dict, Any

from langchain_core.prompts import PromptTemplate
from langchain_community.llms.ollama import Ollama
from langgraph.graph import StateGraph, END

from .wsdl_parser import WsdlInfo, parse_wsdl
from .xml_generator import assemble_full_project_xml

# --- Environment and LLM Configuration ---
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")

# --- Graph State Definition ---
class GraphState(TypedDict):
    """Represents the state of our graph."""
    # Inputs
    wsdl_content: str
    file_name: str
    test_options: List[str]

    # Intermediate state
    wsdl_info: WsdlInfo
    prompt: str
    generated_test_json: str
    parsed_test_json: Dict[str, Any]

    # Final output
    soapui_project_xml: str

    # Utilities
    error_message: str

# --- Node Functions ---

def parse_wsdl_node(state: GraphState) -> GraphState:
    """Parses the WSDL content into a structured format."""
    print("--- Parsing WSDL ---")
    try:
        wsdl_info = parse_wsdl(state["wsdl_content"], state["file_name"])
        return {"wsdl_info": wsdl_info}
    except Exception as e:
        return {"error_message": f"Failed to parse WSDL: {e}"}

def generate_json_prompt_node(state: GraphState) -> GraphState:
    """Generates a prompt to ask the LLM for test case data in JSON format."""
    print("--- Generating JSON Prompt ---")

    if state.get("error_message"):
        return

    operations_summary = [
        {"name": op.name, "input_schema": op.input_schema}
        for op in state["wsdl_info"].operations
    ]

    template = """
You are an expert API test case designer. Your task is to generate a JSON object containing test scenarios for a SOAP API, based on its WSDL operations.

**Instructions:**
1.  Analyze the provided WSDL operations and their input schemas.
2.  For each test type requested by the user ({test_options}), create a key in the JSON object (e.g., "happy_path").
3.  For each test type, generate a list of test case objects.
4.  For each test case, you MUST provide the following keys:
    - `name`: A descriptive name for the test case (e.g., "Convert USD to EUR").
    - `operation`: The name of the WSDL operation to test. This key is mandatory.
    - `payload`: A dictionary of input values for the request body. Create realistic and relevant sample data.
    - `assertions`: A list of assertion objects.
5.  For each assertion object, provide:
    - `type`: The type of assertion. Can be "ValidStatusCode", "SOAPResponse", "SOAPFault", or "XPathMatch".
    - `value`: The value to assert. For "ValidStatusCode", this is the status code. For "XPathMatch" on a negative test, this should be a predicted error message (e.g., "Invalid input"). For "XPathMatch" on a happy path test, this should be a realistic expected value. **This field must not be empty for XPathMatch assertions.**
    - `path`: For "XPathMatch" assertions, the XPath expression to use. For a happy path response, this will typically be `//ns1:{operation}Response/{elementName}`. For a negative test expecting a fault, it will be `//faultstring`.
6.  The output MUST be a single, valid JSON object. Do not include any other text, explanations, or markdown.

**JSON Output Structure Example:**
```json
{{
  "happy_path": [
    {{
      "name": "Convert USD to EUR",
      "operation": "Convert",
      "payload": {{ "source_currency": "USD", "target_currency": "EUR", "amount": 100.0 }},
      "assertions": [
        {{ "type": "ValidStatusCode", "value": "200" }},
        {{ "type": "SOAPResponse" }},
        {{ "type": "XPathMatch", "path": "//ns1:ConvertedAmount", "value": "85.0" }}
      ]
    }}
  ],
  "negative_cases": [
    {{
      "name": "Convert with Invalid Currency",
      "operation": "Convert",
      "payload": {{ "source_currency": "XYZ", "target_currency": "EUR", "amount": 100.0 }},
      "assertions": [
        {{ "type": "SOAPFault" }},
        {{ "type": "XPathMatch", "path": "//faultstring", "value": "Invalid source currency" }}
      ]
    }}
  ]
}}
```

**WSDL Operations Information:**
```json
{operations_summary}
```

Now, generate the JSON object with the test cases based on the user's request for {test_options}.
"""
    prompt = PromptTemplate(
        template=template,
        input_variables=["test_options", "operations_summary"],
    ).format(
        test_options=", ".join(state["test_options"]),
        operations_summary=json.dumps(operations_summary, indent=2),
    )
    return {"prompt": prompt}

def call_llm_for_json_node(state: GraphState) -> GraphState:
    """Calls the LLM to get test case data in JSON format."""
    print(f"--- Calling LLM for JSON ---")
    if state.get("error_message"):
        return
    try:
        llm = Ollama(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.1,
            format="json"
        )
        response = llm.invoke(state["prompt"])
        return {"generated_test_json": response}
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return {"error_message": str(e)}

def parse_json_node(state: GraphState) -> GraphState:
    """Parses the JSON output from the LLM."""
    print("--- Parsing Generated JSON ---")
    if state.get("error_message"):
        return
    try:
        # The response might be a string that looks like a JSON object,
        # or it could be an actual dict if the LLM framework auto-parses it.
        json_string = state["generated_test_json"]
        if isinstance(json_string, dict):
            parsed_json = json_string
        else:
            # Clean the string in case the LLM wrapped it in markdown
            if json_string.strip().startswith("```json"):
                json_string = json_string.strip()[7:-4]
            parsed_json = json.loads(json_string)
        return {"parsed_test_json": parsed_json}
    except json.JSONDecodeError as e:
        return {"error_message": f"Failed to parse JSON from LLM: {e}. Raw output: {state['generated_test_json']}"}

def json_to_xml_node(state: GraphState) -> GraphState:
    """Converts the parsed JSON into a full SoapUI project XML."""
    print("--- Converting JSON to SoapUI XML ---")
    if state.get("error_message"):
        return
    try:
        project_xml = assemble_full_project_xml(
            state["wsdl_info"],
            state["parsed_test_json"],
            state["test_options"]
        )
        return {"soapui_project_xml": project_xml}
    except Exception as e:
        return {"error_message": f"Failed to generate XML from JSON: {e}"}

# --- Graph Assembly ---

workflow = StateGraph(GraphState)

workflow.add_node("parse_wsdl", parse_wsdl_node)
workflow.add_node("generate_json_prompt", generate_json_prompt_node)
workflow.add_node("call_llm_for_json", call_llm_for_json_node)
workflow.add_node("parse_json", parse_json_node)
workflow.add_node("json_to_xml", json_to_xml_node)

def should_continue(state: GraphState):
    """Terminates the graph if an error has occurred."""
    return "END" if state.get("error_message") else "continue"

# Build the graph using conditional edges to handle errors
workflow.set_entry_point("parse_wsdl")
workflow.add_conditional_edges("parse_wsdl", should_continue, {"continue": "generate_json_prompt", "END": END})
workflow.add_conditional_edges("generate_json_prompt", should_continue, {"continue": "call_llm_for_json", "END": END})
workflow.add_conditional_edges("call_llm_for_json", should_continue, {"continue": "parse_json", "END": END})
workflow.add_conditional_edges("parse_json", should_continue, {"continue": "json_to_xml", "END": END})
workflow.add_edge("json_to_xml", END)

graph_app = workflow.compile()

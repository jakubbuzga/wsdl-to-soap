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

    main_template = """<?xml version="1.0" encoding="UTF-8"?>
<con:soapui-project id="{generate_a_uuid}" activeEnvironment="Default" name="Generated-SoapUI-Project" resourceRoot="" soapui-version="5.7.0" xmlns:con="http://eviware.com/soapui/config">
    <con:settings/>
    <con:interface xsi:type="con:WsdlInterface" id="{generate_a_uuid}" name="{WSDL_Binding_Name}" bindingName="{{{WSDL_Target_Namespace}}}{WSDL_Binding_Name}" soapVersion="1_1" definition="{WSDL_File_Name}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <con:settings/>
        <con:endpoints>
            <con:endpoint>{Service_Endpoint_URL}</con:endpoint>
        </con:endpoints>
        <con:operation id="{generate_a_uuid}" isOneWay="false" action="{Operation_Action}" name="{Operation_Name}" bindingOperationName="{Operation_Name}" type="Request-Response">
            <con:settings/>
            <con:call id="{generate_a_uuid}" name="Request 1">
                <con:settings/>
                <con:encoding>UTF-8</con:encoding>
                <con:endpoint>{Service_Endpoint_URL}</con:endpoint>
                <con:request><![CDATA[<!-- Default Request Payload From WSDL -->]]></con:request>
            </con:call>
        </con:operation>

        <!-- LLM: INSERT ALL GENERATED TEST SUITES HERE -->

    </con:interface>
    <con:properties/>
</con:soapui-project>"""

    test_suite_template = """<con:testSuite id="{generate_a_uuid}" name="{suite_name}">
    <con:settings/>
    <con:runType>SEQUENTIAL</con:runType>
    <con:testCase id="{generate_a_uuid}" name="{test_case_name}">
        <con:settings/>

        <!-- LLM: INSERT TEST STEPS HERE -->

    </con:testCase>
</con:testSuite>"""

    happy_path_step_template = """<con:testStep type="request" name="{test_step_name}">
    <con:settings/>
    <con:config xsi:type="con:RequestStep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <con:interface>{WSDL_Binding_Name}</con:interface>
        <con:operation>{Operation_Name}</con:operation>
        <con:request name="{test_step_name}">
            <con:endpoint>{Service_Endpoint_URL}</con:endpoint>
            <con:request><![CDATA[<!-- LLM: INSERT HAPPY PATH SOAP ENVELOPE HERE -->]]></con:request>
            <con:credentials>
                <con:selectedAuthProfile>No Authorization</con:selectedAuthProfile>
            </con:credentials>
            <con:assertion type="Valid HTTP Status Codes" id="{generate_a_uuid}">
                <con:configuration><codes>200</codes></con:configuration>
            </con:assertion>
            <con:assertion type="SOAP Response" id="{generate_a_uuid}"/>
        </con:request>
    </con:config>
</con:testStep>"""

    negative_step_template = """<con:testStep type="request" name="{test_step_name}">
    <con:settings/>
    <con:config xsi:type="con:RequestStep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <con:interface>{WSDL_Binding_Name}</con:interface>
        <con:operation>{Operation_Name}</con:operation>
        <con:request name="{test_step_name}">
            <con:endpoint>{Service_Endpoint_URL}</con:endpoint>
            <con:request><![CDATA[<!-- LLM: INSERT NEGATIVE CASE SOAP ENVELOPE HERE -->]]></con:request>
            <con:credentials>
                <con:selectedAuthProfile>No Authorization</con:selectedAuthProfile>
            </con:credentials>
            <con:assertion type="SOAP Fault" id="{generate_a_uuid}"/>
            <con:assertion type="XPath Match" id="{generate_a_uuid}">
                <con:configuration>
                    <path>//faultstring</path>
                    <content>{Expected_Error_Message}</content>
                    <allowWildcards>false</allowWildcards>
                    <ignoreNamspaceDifferences>true</ignoreNamspaceDifferences>
                    <ignoreComments>true</ignoreComments>
                </con:configuration>
            </con:assertion>
        </con:request>
    </con:config>
</con:testStep>"""

    template = f\"\"\"
You are a world-class expert in SoapUI test automation. Your task is to generate a complete, importable SoapUI project as a single XML file based on the provided WSDL.

The user has requested the following types of test suites: {{test_options}}.

**Rules**
- The output MUST be a single, valid XML document that represents a SoapUI project.
- You MUST follow the exact XML structure provided in the templates below. Pay close attention to every tag and attribute.
- Generate a unique UUID for every id attribute in the project (e.g., a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6).
- For each test type requested by the user (e.g., happy_path, negative_cases), create one `<con:testSuite>` block.
- Inside each test suite, generate one or more `<con:testCase>` blocks based on the scenarios you identify from the WSDL.
- Populate the `<con:request>` CDATA section with the relevant SOAP Envelope payload for each test case.
- Use the appropriate assertion templates for happy path and negative tests.
- Do NOT include any explanations, markdown formatting, or any other text outside of the final XML document.

**1. Main Project Template**
Use this as the main skeleton for the entire file. The test suites you generate will be inserted where indicated.
```xml
{main_template}
```

**2. Test Suite and Test Case Template**
Nest your Test Cases inside this Test Suite structure.
```xml
{test_suite_template}
```

**3. Test Step and Assertion Templates**
A. For HAPPY PATH Test Steps: Use this template for tests that should succeed.
```xml
{happy_path_step_template}
```
B. For NEGATIVE Test Steps: Use this template for tests that should fail and return a SOAP Fault.
```xml
{negative_step_template}
```

Now, based on the WSDL below, generate a complete SoapUI project.

**WSDL Content:**
```xml
{{wsdl_content}}
```
    \"\"\"
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

    **IMPORTANT**: You MUST follow the exact XML structure, namespaces, and conventions for a SoapUI project, as specified in the template-based instructions from the initial request. Do not deviate from the templates.

    User Feedback:
    "{feedback}"

    Original Request Details:
    - Test Suites: {test_options}
    - Original WSDL:
    ```xml
    {wsdl_content}
    ```

    Please regenerate the entire SoapUI project from scratch, applying the user's feedback. The output must be a single, valid XML document. Do not include any text or explanations outside of the XML document.
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

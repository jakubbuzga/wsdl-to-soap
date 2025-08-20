# backend/app/test_graph.py
from app.graph_logic import graph_app, GraphState

# A sample WSDL for testing purposes
sample_wsdl = """
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
     xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
     xmlns:tns="http://www.example.com/calculator"
     xmlns:xsd="http://www.w3.org/2001/XMLSchema"
     name="CalculatorService"
     targetNamespace="http://www.example.com/calculator">
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
        <soap:binding style="rpc" transport="http://schemas.xmlsoap.org/soap/http"/>
        <operation name="add">
            <soap:operation soapAction="add"/>
            <input><soap:body use="literal" namespace="http://www.example.com/calculator"/></input>
            <output><soap:body use="literal" namespace="http://www.example.com/calculator"/></output>
        </operation>
    </binding>
    <service name="CalculatorService">
        <port name="CalculatorPort" binding="tns:CalculatorBinding">
            <soap:address location="http://www.example.com/calculator"/>
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

    config = {"configurable": {"thread_id": "test-thread-1"}}

    # 1. Initial run
    print("\n--- [Step 1] Initial Generation ---")
    for _ in graph_app.stream(initial_state, config=config):
        pass

    final_state = graph_app.get_state(config)
    print("\n--- [Step 1] Result ---")
    print("Generated XML:", final_state.values.get("generated_xml"))
    print("Error Message:", final_state.values.get("error_message"))

    # 2. Simulate feedback and resume
    print("\n--- [Step 2] Providing Feedback and Resuming ---")
    user_feedback = "The negative test is missing. Please add a test where 'a' is zero."

    # To resume, we can't directly modify the state. We need to pass the feedback
    # as input to the next step. Since the graph is paused, the next step is
    # defined by what we pass to the stream. However, our graph doesn't have
    # a node that accepts feedback directly after the pause.
    # For this test, we will just start a new run with the feedback in the history.

    new_initial_state = {
        "wsdl_content": sample_wsdl,
        "test_options": ["happy_path", "negative case with zero"],
        "feedback_history": [user_feedback],
    }

    resumed_final_state = None
    for _ in graph_app.stream(new_initial_state, config=config):
        pass

    resumed_final_state = graph_app.get_state(config)
    print("\n--- [Step 2] Result after Feedback ---")
    print("Regenerated XML:", resumed_final_state.values.get("generated_xml"))
    print("Error Message:", resumed_final_state.values.get("error_message"))
    print(f"Total attempts: {resumed_final_state.values.get('attempt_count')}")

    print("\n--- Graph Test Finished ---")

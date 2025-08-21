# wsdl-test-generator/backend/app/xml_generator.py
import uuid
from typing import List, Dict, Any
from .wsdl_parser import WsdlInfo, WsdlOperation

def _generate_uuid():
    return str(uuid.uuid4())

def _build_request_payload(operation: WsdlOperation, payload_data: Dict[str, Any], target_namespace: str) -> str:
    """Builds the SOAP Envelope from payload data."""
    body = ""
    for key, value in payload_data.items():
        body += f"<{key}>{value}</{key}>"

    return f"""<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="{target_namespace}">
   <soap:Header/>
   <soap:Body>
      <tns:{operation.name}>
         {body}
      </tns:{operation.name}>
   </soap:Body>
</soap:Envelope>"""

def create_test_step_xml(test_case_data: Dict[str, Any], wsdl_info: WsdlInfo, test_type: str) -> str:
    """Creates the XML for a single SoapUI test step."""
    op_name = test_case_data["operation"]
    operation = next((op for op in wsdl_info.operations if op.name == op_name), None)
    if not operation:
        return ""

    test_step_name = test_case_data["name"]
    request_payload = _build_request_payload(operation, test_case_data["payload"], wsdl_info.target_namespace)

    assertions_xml = []
    for assertion in test_case_data.get("assertions", []):
        assertion_type = assertion.get("type")
        if assertion_type == "ValidStatusCode":
            assertions_xml.append(f'<con:assertion type="Valid HTTP Status Codes" id="{_generate_uuid()}"><con:configuration><codes>{assertion.get("value", "200")}</codes></con:configuration></con:assertion>')
        elif assertion_type == "SOAPResponse":
            assertions_xml.append(f'<con:assertion type="SOAP Response" id="{_generate_uuid()}"/>')
        elif assertion_type == "SOAPFault":
            assertions_xml.append(f'<con:assertion type="SOAP Fault" id="{_generate_uuid()}"/>')
        elif assertion_type == "XPathMatch":
            path = assertion.get("path", "")
            value = assertion.get("value", "")
            # Only add the assertion if there is a value to check for.
            if path and value:
                assertions_xml.append(f"""<con:assertion type="XPath Match" id="{_generate_uuid()}">
                    <con:configuration>
                        <path>{path}</path>
                        <content>{value}</content>
                        <allowWildcards>false</allowWildcards>
                        <ignoreNamspaceDifferences>true</ignoreNamspaceDifferences>
                        <ignoreComments>true</ignoreComments>
                    </con:configuration>
                </con:assertion>""")

    template = """<con:testStep type="request" name="{test_step_name}">
    <con:settings/>
    <con:config xsi:type="con:RequestStep" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <con:interface>{WSDL_Binding_Name}</con:interface>
        <con:operation>{Operation_Name}</con:operation>
        <con:request name="{test_step_name}">
            <con:endpoint>{Service_Endpoint_URL}</con:endpoint>
            <con:request><![CDATA[{request_payload}]]></con:request>
            <con:credentials><con:selectedAuthProfile>No Authorization</con:selectedAuthProfile></con:credentials>
            {assertions_xml}
        </con:request>
    </con:config>
</con:testStep>"""
    return template.format(
        test_step_name=test_step_name,
        WSDL_Binding_Name=wsdl_info.binding_name,
        Operation_Name=op_name,
        Service_Endpoint_URL=wsdl_info.service_endpoint_url,
        request_payload=request_payload,
        assertions_xml="\n".join(assertions_xml)
    )

def create_test_case_xml(test_case_data: Dict[str, Any], wsdl_info: WsdlInfo, test_type: str) -> str:
    """Creates the XML for a single SoapUI test case."""
    test_case_name = test_case_data["name"]
    test_steps_xml = create_test_step_xml(test_case_data, wsdl_info, test_type)

    template = """<con:testCase id="{generate_a_uuid}" name="{test_case_name}">
    <con:settings/>
    {test_steps_xml}
</con:testCase>"""
    return template.format(
        generate_a_uuid=_generate_uuid(),
        test_case_name=test_case_name,
        test_steps_xml=test_steps_xml
    )

def create_test_suite_xml(suite_name: str, test_cases_data: List[Dict[str, Any]], wsdl_info: WsdlInfo, test_type: str) -> str:
    """Creates the XML for a SoapUI test suite."""
    test_cases_xml = [
        create_test_case_xml(tc, wsdl_info, test_type) for tc in test_cases_data
    ]

    template = """<con:testSuite id="{generate_a_uuid}" name="{suite_name}">
    <con:settings/>
    <con:runType>SEQUENTIAL</con:runType>
    {test_cases_xml}
</con:testSuite>"""
    return template.format(
        generate_a_uuid=_generate_uuid(),
        suite_name=suite_name,
        test_cases_xml="\n".join(test_cases_xml)
    )

def assemble_full_project_xml(wsdl_info: WsdlInfo, test_json: Dict[str, Any], test_options: List[str]) -> str:
    """Assembles the complete SoapUI project XML."""

    test_suites_xml = []
    for test_type in test_options:
        if test_type in test_json:
            suite_name = test_type.replace("_", " ").title() + " Tests"
            test_cases_data = test_json[test_type]
            test_suites_xml.append(create_test_suite_xml(suite_name, test_cases_data, wsdl_info, test_type))

    operations_xml = []
    for op in wsdl_info.operations:
        operations_xml.append(f'<con:operation id="{_generate_uuid()}" isOneWay="false" action="{op.action}" name="{op.name}" bindingOperationName="{op.name}" type="Request-Response"><con:settings/></con:operation>')

    main_template = """<?xml version="1.0" encoding="UTF-8"?>
<con:soapui-project id="{project_id}" activeEnvironment="Default" name="{project_name}" resourceRoot="" soapui-version="5.7.0" xmlns:con="http://eviware.com/soapui/config">
    <con:settings/>
    <con:interface xsi:type="con:WsdlInterface" id="{interface_id}" name="{interface_name}" bindingName="{{{target_namespace}}}{interface_name}" soapVersion="1_1" definition="{wsdl_file_name}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <con:settings/>
        <con:endpoints>
            <con:endpoint>{service_endpoint}</con:endpoint>
        </con:endpoints>
        {operations_xml}
    </con:interface>
    {test_suites_xml}
    <con:properties/>
</con:soapui-project>"""

    return main_template.format(
        project_id=_generate_uuid(),
        project_name=f"{wsdl_info.binding_name}-SoapUI-Project",
        interface_id=_generate_uuid(),
        interface_name=wsdl_info.binding_name,
        target_namespace=wsdl_info.target_namespace,
        wsdl_file_name=wsdl_info.file_name,
        service_endpoint=wsdl_info.service_endpoint_url,
        operations_xml="\n".join(operations_xml),
        test_suites_xml="\n".join(test_suites_xml)
    )

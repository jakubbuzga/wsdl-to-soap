# wsdl-test-generator/backend/app/wsdl_parser.py
from pydantic import BaseModel
from typing import List, Dict, Any
from io import BytesIO
from lxml import etree

class WsdlOperation(BaseModel):
    name: str
    action: str
    input_schema: Dict[str, Any]

class WsdlInfo(BaseModel):
    file_name: str
    binding_name: str
    target_namespace: str
    service_endpoint_url: str
    operations: List[WsdlOperation]

def _get_element_schema(element, namespaces: Dict[str, str]) -> Dict[str, Any]:
    """Recursively builds a dictionary schema for a given XSD element."""
    schema = {}
    if element is None:
        return schema

    # Find all child elements (could be sequence, choice, etc.)
    child_elements_container = element.find('.//xsd:sequence', namespaces)
    if child_elements_container is None:
        child_elements_container = element.find('.//xsd:choice', namespaces)

    if child_elements_container is not None:
        for child in child_elements_container.findall('xsd:element', namespaces):
            child_name = child.get('name')
            child_type = child.get('type', 'string').split(':')[-1]
            if child_name:
                schema[child_name] = child_type
    return schema


def parse_wsdl(wsdl_content: str, file_name: str = "service.wsdl") -> WsdlInfo:
    """
    Parses the WSDL content using lxml to extract key information.
    """
    try:
        # Use recover=True to handle potentially malformed XML gracefully
        parser = etree.XMLParser(recover=True)
        tree = etree.fromstring(wsdl_content.encode('utf-8'), parser=parser)

        namespaces = {
            'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
            'soap': 'http://schemas.xmlsoap.org/wsdl/soap/',
            'soap12': 'http://schemas.xmlsoap.org/wsdl/soap12/',
            'xsd': 'http://www.w3.org/2001/XMLSchema'
        }

        target_namespace = tree.get('targetNamespace')

        binding = tree.find('.//wsdl:binding', namespaces)
        if binding is None:
            raise ValueError("Could not find wsdl:binding in the WSDL.")
        binding_name = binding.get('name')

        soap_address = tree.find('.//wsdl:service/wsdl:port/soap:address', namespaces)
        if soap_address is None:
            soap_address = tree.find('.//wsdl:service/wsdl:port/soap12:address', namespaces)
        if soap_address is None:
            raise ValueError("Could not find soap:address or soap12:address in the WSDL port.")
        service_endpoint_url = soap_address.get("location")

        operations = []
        port_type_name = binding.get('type').split(':')[-1]
        port_type = tree.find(f".//wsdl:portType[@name='{port_type_name}']", namespaces)

        if port_type is not None:
            for op in port_type.findall('wsdl:operation', namespaces):
                op_name = op.get('name')

                # Find corresponding soap action from binding
                binding_op = binding.find(f"wsdl:operation[@name='{op_name}']", namespaces)
                soap_action = ''
                if binding_op is not None:
                    soap_op = binding_op.find('soap:operation', namespaces)
                    if soap_op is not None:
                        soap_action = soap_op.get('soapAction', '')

                input_schema = {}
                input_tag = op.find('wsdl:input', namespaces)
                if input_tag is not None:
                    message_name = input_tag.get('message').split(':')[-1]
                    message = tree.find(f".//wsdl:message[@name='{message_name}']", namespaces)
                    if message is not None:
                        part = message.find('wsdl:part', namespaces)
                        if part is not None and part.get('element') is not None:
                            element_name = part.get('element').split(':')[-1]
                            element = tree.find(f".//xsd:element[@name='{element_name}']", namespaces)
                            if element is not None:
                                input_schema = _get_element_schema(element, namespaces)

                wsdl_op = WsdlOperation(
                    name=op_name,
                    action=soap_action,
                    input_schema=input_schema
                )
                operations.append(wsdl_op)

        return WsdlInfo(
            file_name=file_name,
            binding_name=binding_name,
            target_namespace=target_namespace,
            service_endpoint_url=service_endpoint_url,
            operations=operations
        )

    except Exception as e:
        print(f"Error parsing WSDL with lxml: {e}")
        raise ValueError(f"Failed to parse WSDL with lxml: {e}")

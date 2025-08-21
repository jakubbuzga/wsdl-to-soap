# wsdl-test-generator/backend/app/wsdl_parser.py
from pydantic import BaseModel
from typing import List, Dict, Any
import zeep
from zeep.wsdl import Document
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

def parse_wsdl(wsdl_content: str, file_name: str = "service.wsdl") -> WsdlInfo:
    """
    Parses the WSDL content to extract key information required for test generation.
    """
    try:
        wsdl_file = BytesIO(wsdl_content.encode('utf-8'))
        doc = Document(wsdl_file, None)

        # This makes some simplifying assumptions, e.g., one service, one port
        service = list(doc.services.values())[0]
        port = list(service.ports.values())[0]
        binding = port.binding

        # The 'address' attribute is not directly on the port object.
        # We need to inspect the raw XML element to find the soap:address location.
        soap_address = port.element.find('{http://schemas.xmlsoap.org/wsdl/soap/}address')
        if soap_address is None:
            raise ValueError("Could not find soap:address in the WSDL port.")
        service_endpoint_url = soap_address.get("location")

        binding_name = binding.name
        target_namespace = doc.target_namespace

        operations = []
        for op_name, operation in binding.operations.items():

            input_schema = {}
            # The input part can be complex. We'll try to get the elements
            # of the input message's part.
            if operation.input.body.type:
                input_part = operation.input.body.type
                if hasattr(input_part, 'elements'):
                     for elem_name, elem_type in input_part.elements:
                        input_schema[elem_name] = elem_type.name if hasattr(elem_type, 'name') else 'anyType'

            wsdl_op = WsdlOperation(
                name=op_name,
                action=operation.soapaction,
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
        print(f"Error parsing WSDL: {e}")
        # Re-raise or handle as a custom exception
        raise ValueError(f"Failed to parse WSDL: {e}")

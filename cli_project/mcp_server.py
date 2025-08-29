from mcp.server.fastmcp import FastMCP
from pydantic import Field
# from mcp.types import Tool, Resource, Prompt
# from typing import Dict, Any

mcp = FastMCP("DocumentMCP", log_level="ERROR")


docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
}

#read a doc
@mcp.tool(
    name="read_doc_contents",
    description="Read the contents of a document and return it as a string.",
)
def read_document(
    doc_id: str = Field(description="The ID of the document to read.")
):
    if doc_id not in docs:
        raise ValueError(f"Document {doc_id} not found.")
    return docs[doc_id]


#tool to edit a doc
@mcp.tool(
    name="edit_document",
    description="Edit a document by replacing a string in the documents content with a new string.",
)
def edit_document(
    doc_id: str = Field(description="ID of the document that will be edited."),
    old_string: str = Field(description="The text to replace. Must match exactly, including white space."),
    new_string: str = Field(description="The new text to insert in place of old text."),
):
    if doc_id not in docs:
        raise ValueError(f"Document {doc_id} not found.")
    docs[doc_id] = docs[doc_id].replace(old_string, new_string)




if __name__ == "__main__":
    mcp.run(transport="stdio")

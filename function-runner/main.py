from typing import Literal, Union, List
import toml

from fastapi import FastAPI
from interpreter.code_interpreters.create_code_interpreter import \
    create_code_interpreter
from interpreter.code_interpreters.subprocess_code_interpreter import \
    SubprocessCodeInterpreter
from pydantic import BaseModel

app = FastAPI()

Role = Literal["system", "user", "assistant", "function"]


class UserMessage(BaseModel):
    role: Role = "user"
    content: str


class FunctionArgument(BaseModel):
    language: str
    code: str


class FunctionCall(BaseModel):
    name: str
    arguments: str
    parsed_arguments: FunctionArgument


class FunctionResult(BaseModel):
    role: Role = "function"
    name: str
    content: str


class AssistantMessage(BaseModel):
    role: Role = "assistant"
    content: str


Message = Union[UserMessage, FunctionCall, FunctionResult, AssistantMessage]


@app.post("/run/")
def execute_code(function_argument: FunctionArgument) -> FunctionResult:
    code_interpreter: SubprocessCodeInterpreter = create_code_interpreter(function_argument.language)
    code_interpreter.run(function_argument.code)
    output = ""
    for line in code_interpreter.run(function_argument.code):
        output_line = line.get("output", "")
        output += f"\n{output_line}" if output else output_line
    print(
        {
            "message": "Run code.",
            "language": function_argument.language,
            "code": function_argument.code,
            "output": output,
        }
    )

    return FunctionResult(
        role="function",
        name="run_code",
        content=output.strip(),
    )

EXCLUDE_PACKAGES = {
    "open-interpreter",
    "python",
    "pydantic",
    "fastapi",
    "uvicorn",
    "python-json-logger",
    "toml",
    "google-cloud-storage",
    "toml",
}

def get_python_packages() -> List[str]:
    with open("pyproject.toml") as pyproject_file:
        pyproject = toml.load(pyproject_file)
    packages = pyproject["tool"]["poetry"]["dependencies"]
    package_names = [package_name for package_name in packages.keys() if package_name not in EXCLUDE_PACKAGES]
    return package_names


class PackagesResponse(BaseModel):
    packages : List[str]

@app.get("/packages/")
def get_packages(language: str) -> PackagesResponse:
    package_names = []
    if language == "python":
        package_names = get_python_packages()
    return { "packages": package_names }
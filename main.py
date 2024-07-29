import logging
import os
import subprocess
from logging import getLogger

import boto3
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_aws import ChatBedrock
from pydantic import BaseModel
from user_session import ChatSession, ChatSessionManager

logging.basicConfig(level=logging.INFO)
logger = getLogger(__name__)
app = FastAPI()
router = APIRouter()

os.environ["AWS_PROFILE"] = "fab-geekle"
origins = [
    "*",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# fix the region_name -> us-west-2
bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-west-2")
session_manager = ChatSessionManager()


# Function to clone repository and list files
def clone_and_list_files(repo_url):
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    if os.path.exists(repo_name):
        subprocess.run(["rm", "-rf", repo_name])
    subprocess.run(["git", "clone", repo_url])
    files = os.listdir(repo_name)
    return repo_name, files


# Function to read the content of a file
def read_file_content(repo_name, filename):
    with open(os.path.join(repo_name, filename), 'r') as file:
        return file.read()

def get_response_from_llm(
        input_prompt: str,
        project_type: str,
        file_content: str,
        model_id: str,
        bedrock_client: boto3.client,
):
    logger.info(f"Getting response from LLM with model_id: {model_id}")
    logger.info(f"Input prompt: {input_prompt}")
    processed_prompt = generate_prompt_for_command(
        project_type, file_content
    )
    logger.info(f"Processed prompt: {processed_prompt}")
    print(processed_prompt)
    llm = ChatBedrock(
        model_id=model_id, client=bedrock_client, model_kwargs={
            "temperature": 0.75,
            "max_tokens": 2000,
            "top_p": 0.9,
        }
    )
    response = llm.invoke(processed_prompt)
    content = response.content
    original_response = content
    logger.info(f"Response from LLM: {content}")
    # print(content)

    return content


def generate_prompt_for_command(
        project_type: str, file_content: str
):
    prompt = f"""
        The project type is {project_type}. Create a bash script to install and execute the project based on the following file content:
        {file_content}
        Only provide the bash script, no other content.
        """
    return prompt

def determine_project_type_and_instructions(files, repo_name):
    project_files = {
        'package.json': 'Node.js',
        'requirements.txt': 'Python',
        'pom.xml': 'Java (Maven)',
        'build.gradle': 'Java (Gradle)',
        'Gemfile': 'Ruby on Rails',
        'composer.json': 'PHP',
        'go.mod': 'Go',
        'Cargo.toml': 'Rust',
        'bun.lockb': 'Bun',
        'Package.swift': 'Swift',
        'NuGet.config': 'C# (NuGet)',
        'mix.exs': 'Elixir (Mix)',
        'Makefile': 'Make',
        # Add more file types and project types as needed
    }

    for filename, project_type in project_files.items():
        if filename in files:
            file_content = read_file_content(repo_name, filename)
            return project_type, file_content

    return "Unknown", ""


# Function to clone repository and list files
def clone_and_list_files(repo_url):
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    if os.path.exists(repo_name):
        subprocess.run(["rm", "-rf", repo_name])
    subprocess.run(["git", "clone", repo_url])
    files = os.listdir(repo_name)
    return repo_name, files


# Function to read the content of a file
def read_file_content(repo_name, filename):
    with open(os.path.join(repo_name, filename), 'r') as file:
        return file.read()

@router.post("/dashboard")
async def generate_graph(request: Request):
    # try:
    request = await request.json();
    print("Raw request body:", request)
    repo_url = request.get("git_url");
    repo_name, files = clone_and_list_files(repo_url)
    project_type, file_content = determine_project_type_and_instructions(files, repo_name)
    processed_prompt = generate_prompt_for_command(project_type, file_content)
    if project_type == "Unknown":
        instructions = "#!/bin/bash\n# The project type could not be determined automatically. Please check the repository's README file for setup instructions."
    else:

        llm = ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0", client=bedrock, model_kwargs={
                "temperature": 0.75,
                "max_tokens": 2000,
                "top_p": 0.9,
            }
        )
        # Generate instructions using LangChain
        instructions = llm.invoke(processed_prompt)
    print(instructions)

    return instructions
app.include_router(router)


class ModelKWArgs(BaseModel):
    modelParameter: dict = {
        "temperature": 0.75,
        "max_tokens": 2000,
        "top_p": 0.9,
    }


class RequestModel(ModelKWArgs):
    userID: str
    requestID: str
    user_input: str
    modelID: str = "anthropic.claude-3-haiku-20240307-v1:0"


class MermaidRequest(BaseModel):
    userID: str


def chat_llm_no_stream(request: RequestModel, chat_session: ChatSession) -> dict:
    chat_model = ChatBedrock(
        model_id=request.modelID,
        client=bedrock,
        model_kwargs=request.modelParameter,
        streaming=True,
    )
    if len(chat_session.chats) != 0:
        wants_to_draw_prompt = f"""
            There has been a conversation between the user and the chatbot about providing github links repository.
            Given the user's input: {request.user_input}
            When  user imply that they have chosen a solution or chose a number ?
            Respond with 
            <p id="hiddenGitHub" hidden>githublink.git</p>.
            <p>Loading and launching repo in sandbox</p>.
             
        """
        wants_to_draw = chat_model.invoke(wants_to_draw_prompt).content
        if "Yes" in wants_to_draw:
            chat_session.add_chat(request.user_input, wants_to_draw)
            return {
                "user_input": request.user_input,
                "wantsToDraw": True,
            }

    text_input = request.user_input
    if len(chat_session.chats) == 0:
        initial_context = """
             
        I will now give you my question or task, and you can ask me subsequent questions one by one.

        Please format your output in HTML and provide public GitHub repo links with a 4-line max summary of what each repo does. 
        Here's an example of how the output should look:
        <ol>
          <li>
            <a href="github link 1">github link 1</a>
            <p>Repo 1 does X. It is useful for Y.</p>
          </li>
          <li>
            <a href="github link 2">github link 2</a>
            <p>Repo 2 does A. It is designed to B.</p>
          </li>
          <li>
            <a href="github link 3">github link 3</a>
            <p>Repo 3 does M. It helps in N.</p>
          </li>
        </ol>
        Do suggest 1 to 4 public repos that implement my question.
        
        Provide the links always.
        
        Ask the user which option they prefer.
        
        Only ask the question and do not number your questions.
        """
        text_input = initial_context + text_input
    else:
        text_input = f"""
            Given the following conversation of chatbot and user:
            {chat_session.str_chat()}
            Proceed with new user response: "{text_input}"
            Respond immediately with a repository URL if you found one. Ensure the GitHub link provided ends with '.git'.
        """

    response = chat_model.invoke(text_input)
    logger.info(f"Task created for user: {request.userID}")
    logger.info(f"User chat history: {chat_session.chats}")

    response_content = response.content
    git_url = next((line.strip() for line in response_content.split() if line.strip().endswith('.git')), None)
    chat_session.add_chat(request.user_input, response_content)
    return {
        "user_input": request.user_input,
        "model_output": response_content,
        "wantsToDraw": False,
        "repository": git_url
    }

def generate_mermaid(chat_session: ChatSession) -> dict:
    model = ChatBedrock(
        model_id=chat_session.model_id,
        client=bedrock,
        model_kwargs=chat_session.model_kwargs,
    )
    if not chat_session.chats:
        raise HTTPException(status_code=404, detail="Please provide user requirements.")
    prompt = f"""
    Given the following conversation:
    {chat_session.str_chat()}
    Generate a mermaid code to represent the architecture.    
    Make sure each component's name is detailed.
    Also write texts on the arrows to represent the flow of data. 
        For ex. F -->|Transaction Succeeds| G[Publish PRODUCT_PURCHASED event] --> END
    Only generate the code and nothing else.
    Include as many components as possible and each component should have a detailed name.
    Use colors and styles to differentiate between components. Be creative.
    """
    response = model.invoke(prompt)
    content = response.content

    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    if content.startswith("mermaid"):
        content = content[7:]

    last_index = content.rfind("```")
    if last_index != -1:
        content = content[:last_index]

    return {
        "mermaid_code": content,
        "userID": chat_session.user_id,
    }


@app.post("/chat-llm/")
def chat_llm(request: RequestModel):
    chat_session = session_manager.get_session(request.userID)
    try:
        response = chat_llm_no_stream(request, chat_session)
        chat_session.user_id = request.userID
        chat_session.request_id = request.requestID
        chat_session.model_id = request.modelID
        chat_session.model_kwargs = request.modelParameter
        return response
    except Exception as e:
        logger.error(f"Error generating detailed solution: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generating detailed solution: {str(e)}"
        )


# @app.post("/generate-mermaid/")
# def generate_mermaid_code(mermaid_request: MermaidRequest):
#     chat_session = session_manager.get_session(mermaid_request.userID)
#     mermaid_response = generate_mermaid(chat_session)
#     return mermaid_response
#
#
# @app.post("/get-user-history/")
# def get_user_history(mermaid_request: MermaidRequest):
#     chat_session = session_manager.get_session(mermaid_request.userID)
#     chat_history = chat_session.chats
#     return {"userID": mermaid_request.userID, "chat_history": chat_history}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

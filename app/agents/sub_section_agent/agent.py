from google.adk.agents.llm_agent import Agent
from google.adk.agents import LlmAgent

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm

load_dotenv()
# root_agent = Agent(
#     model=LiteLlm(model="openai/gpt-4o"),
#     name='root_agent',
#     description='A helpful assistant for user questions.',
#     instruction='Answer user questions to the best of your knowledge',
# )

root_agent = LlmAgent(
    model=LiteLlm(model="openai/gpt-4o"), # LiteLLM model string format
    name="openai_agent",
    description='A helpful assistant for user questions.',
    instruction="You are an experienced researcher, published in many renowned journal in the Information System field.",
    # ... other agent parameters
)
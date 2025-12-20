from app.agents.orchestrator import OrchestratorAgent
from app.core.models import UserMessage, AgentResponse
import os
import asyncio
from dotenv import load_dotenv

import mlflow

load_dotenv()

async def main():
    """
    Main chat interface with support for clarification flow.
    
    Handles the conversation loop where:
    - User sends message
    - System may ask for clarification
    - User can respond to clarification
    - System provides final answer
    """
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_NAME"))
    # Initialize the orchestrator with all agents
    chatbot = OrchestratorAgent(
        model='azure:gpt-5-nano',
        instructions='Be helpful and concise.'
    )
    
    print("Chatbot initialized. Type your messages (or 'quit' to exit)")
    print("-" * 50)
    
    # Track if we're waiting for clarification
    pending_clarification = False
    original_message = None
    
    # Conversation loop
    while True:
        if pending_clarification:
            prompt = "\n[Clarification] You: "
        else:
            prompt = "\nYou: "
        
        user_input = input(prompt).strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        # Create user message
        if pending_clarification:
            # Combine original message with clarification response
            combined_message = f"{original_message}\n\n[Clarification response]: {user_input}"
            user_message = UserMessage(content=combined_message)
            pending_clarification = False
            original_message = None
        else:
            user_message = UserMessage(content=user_input)
        
        # Get response from orchestrator
        response: AgentResponse = await chatbot.chat(user_message)
        
        # Check if clarification is needed
        if response.requires_followup:
            print(f"Bot: {response.message}")
            pending_clarification = True
            original_message = user_input
        else:
            print(f"Bot: {response.message}")
            
            # Optionally show metadata
            if response.metadata:
                intent = response.metadata.get('intent_type', 'unknown')
                print(f"[Intent: {intent}]")


if __name__ == "__main__":
    asyncio.run(main())
